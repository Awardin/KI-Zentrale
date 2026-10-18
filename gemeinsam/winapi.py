"""Windows-Abfragen ohne Zusatzpakete.

Prozesse, lauschende Ports, VRAM je Prozess (Leistungsindikator
"GPU Process Memory") und die Zuordnung Windows-Grafikadapter -> PCI-Steckplatz.
"""
import ctypes
import ctypes.wintypes as wt
import os
import socket
import struct
import subprocess

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_ntdll = ctypes.WinDLL('ntdll')
_iphlp = ctypes.WinDLL('iphlpapi')
_gdi32 = ctypes.WinDLL('gdi32')
_pdh = ctypes.WinDLL('pdh')
_user32 = ctypes.WinDLL('user32', use_last_error=True)

_INVALID_HANDLE = ctypes.c_void_p(-1).value
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_BREAKAWAY_FROM_JOB = 0x01000000

_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.OpenProcess.restype = wt.HANDLE
_k32.CloseHandle.argtypes = [wt.HANDLE]
_k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
_k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
_k32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
_k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
_k32.CreateToolhelp32Snapshot.argtypes = [wt.DWORD, wt.DWORD]
_k32.CreateToolhelp32Snapshot.restype = wt.HANDLE
_k32.Process32FirstW.argtypes = [wt.HANDLE, ctypes.c_void_p]
_k32.Process32NextW.argtypes = [wt.HANDLE, ctypes.c_void_p]
_ntdll.NtQueryInformationProcess.argtypes = [wt.HANDLE, wt.ULONG, ctypes.c_void_p, wt.ULONG, ctypes.POINTER(wt.ULONG)]
_ntdll.NtQueryInformationProcess.restype = wt.LONG
_iphlp.GetExtendedTcpTable.argtypes = [ctypes.c_void_p, ctypes.POINTER(wt.DWORD), wt.BOOL, wt.ULONG, ctypes.c_int, wt.ULONG]
_iphlp.GetExtendedTcpTable.restype = wt.DWORD
_pdh.PdhOpenQueryW.argtypes = [wt.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
_pdh.PdhAddEnglishCounterW.argtypes = [ctypes.c_void_p, wt.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
_pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
_pdh.PdhGetFormattedCounterArrayW.argtypes = [ctypes.c_void_p, wt.DWORD, ctypes.POINTER(wt.DWORD), ctypes.POINTER(wt.DWORD), ctypes.c_void_p]
_pdh.PdhGetFormattedCounterArrayW.restype = wt.DWORD
_WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
_user32.EnumWindows.argtypes = [_WNDENUMPROC, wt.LPARAM]
_user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
_user32.IsWindowVisible.argtypes = [wt.HWND]
_user32.GetWindowTextLengthW.argtypes = [wt.HWND]
_user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
_user32.GetWindow.restype = wt.HWND
_user32.IsIconic.argtypes = [wt.HWND]
_user32.ShowWindow.argtypes = [wt.HWND, ctypes.c_int]
_user32.SetForegroundWindow.argtypes = [wt.HWND]
_user32.PostMessageW.argtypes = [wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM]
_user32.PostMessageW.restype = wt.BOOL


# ---------------------------------------------------------------- Arbeitsspeicher

class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [('dwLength', wt.DWORD), ('dwMemoryLoad', wt.DWORD)] + [
        (n, ctypes.c_ulonglong) for n in ('ullTotalPhys', 'ullAvailPhys', 'ullTotalPageFile',
                                        'ullAvailPageFile', 'ullTotalVirtual', 'ullAvailVirtual',
                                        'ullAvailExtendedVirtual')]


_k32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MEMORYSTATUSEX)]
_k32.GlobalMemoryStatusEx.restype = wt.BOOL


def freier_arbeitsspeicher_mib():
    """Verfügbarer physischer Arbeitsspeicher in MiB."""
    status = _MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(status)
    if not _k32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise ctypes.WinError(ctypes.get_last_error())
    return status.ullAvailPhys / 1048576


# ---------------------------------------------------------------- Prozesse

class _PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [('dwSize', wt.DWORD), ('cntUsage', wt.DWORD), ('th32ProcessID', wt.DWORD),
                ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wt.DWORD),
                ('cntThreads', wt.DWORD), ('th32ParentProcessID', wt.DWORD),
                ('pcPriClassBase', ctypes.c_long), ('dwFlags', wt.DWORD),
                ('szExeFile', ctypes.c_wchar * 260)]


def prozesse():
    """{pid: (eltern_pid, programmname)} aller laufenden Prozesse."""
    snap = _k32.CreateToolhelp32Snapshot(0x2, 0)
    if not snap or snap == _INVALID_HANDLE:
        return {}
    out = {}
    try:
        e = _PROCESSENTRY32W()
        e.dwSize = ctypes.sizeof(e)
        ok = _k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            out[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile)
            ok = _k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        _k32.CloseHandle(snap)
    return out


def prozess_details(pid):
    """(Programmpfad, Kommandozeile, Startzeit) oder None, wenn nicht lesbar."""
    h = _k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return None
    try:
        buf = ctypes.create_unicode_buffer(32768)
        n = wt.DWORD(32768)
        pfad = buf.value if _k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) else None
        cmd = None
        laenge = wt.ULONG(0)
        _ntdll.NtQueryInformationProcess(h, 60, None, 0, ctypes.byref(laenge))  # ProcessCommandLineInformation
        if laenge.value:
            b = ctypes.create_string_buffer(laenge.value)
            if _ntdll.NtQueryInformationProcess(h, 60, b, laenge.value, ctypes.byref(laenge)) == 0:
                zeichen = struct.unpack_from('<H', b, 0)[0] // 2
                zeiger = struct.unpack_from('<Q', b, 8)[0]
                cmd = ctypes.wstring_at(zeiger, zeichen) if zeiger else ''
        zeiten = [wt.FILETIME() for _ in range(4)]
        start = None
        if _k32.GetProcessTimes(h, *[ctypes.byref(z) for z in zeiten]):
            start = (zeiten[0].dwHighDateTime << 32) | zeiten[0].dwLowDateTime
        return pfad, cmd, start
    finally:
        _k32.CloseHandle(h)


WAIT_OBJECT_0, WAIT_TIMEOUT = 0x0, 0x102


def prozess_oeffnen(pid):
    """Handle zum Beobachten eines Prozesses oder None. Vor einer langen Aufgabe öffnen und bis zu ihrem Ende halten:
    der Handle hält genau diesen Prozess fest, eine gespeicherte PID könnte später einem anderen gehören."""
    if not pid:
        return None
    return _k32.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid)) or None


def prozess_beendet(handle):
    """True nur bei bestätigtem Ende, False, solange der Prozess läuft, None, wenn es sich nicht feststellen lässt
    (kein Handle, Fehler der Abfrage)."""
    if not handle:
        return None
    r = _k32.WaitForSingleObject(handle, 0)
    if r == WAIT_OBJECT_0:
        return True
    if r == WAIT_TIMEOUT:
        return False
    return None


def handle_schliessen(handle):
    if handle:
        _k32.CloseHandle(handle)


def beenden(pid, warten_ms=8000):
    """Beendet genau diesen Prozess und wartet auf sein Ende."""
    h = _k32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False, pid)
    if not h:
        return False
    try:
        if not _k32.TerminateProcess(h, 1):
            return False
        _k32.WaitForSingleObject(h, warten_ms)
        return True
    finally:
        _k32.CloseHandle(h)


_GEERBT_NICHT_WEITERGEBEN = ('ELECTRON_RUN_AS_NODE', 'ELECTRON_NO_ATTACH_CONSOLE', 'CHROME_CRASHPAD_PIPE_NAME')


def starte_losgeloest(argv, arbeitsordner, env=None, log_basis=None):
    """Startet ein Programm ohne Konsolenfenster, das unabhängig von der Zentrale weiterläuft."""
    # Wurde die Zentrale aus einer Electron-App heraus gestartet, würden diese Variablen
    # andere Electron-Programme (z. B. DSH) stören.
    env = {k: v for k, v in (env if env is not None else os.environ).items() if k.upper() not in _GEERBT_NICHT_WEITERGEBEN}
    ausgaben = []
    try:
        if log_basis:
            ausgaben = [open(log_basis + '.out.log', 'ab'), open(log_basis + '.err.log', 'ab')]
        kwargs = dict(cwd=arbeitsordner, env=env, stdin=subprocess.DEVNULL,
                      stdout=ausgaben[0] if ausgaben else subprocess.DEVNULL,
                      stderr=ausgaben[1] if ausgaben else subprocess.DEVNULL, close_fds=True)
        basis = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
        try:
            return subprocess.Popen(argv, creationflags=basis | CREATE_BREAKAWAY_FROM_JOB, **kwargs)
        except OSError:
            return subprocess.Popen(argv, creationflags=basis, **kwargs)
    finally:
        for f in ausgaben:
            f.close()


# ---------------------------------------------------------------- Ports

def lauschende_ports():
    """[(adresse, port, pid)] aller TCP-Ports im Zustand LISTEN (IPv4 und IPv6)."""
    out = []
    for familie, zeilenlaenge in ((socket.AF_INET, 24), (socket.AF_INET6, 56)):
        groesse = wt.DWORD(0)
        _iphlp.GetExtendedTcpTable(None, ctypes.byref(groesse), False, familie, 3, 0)  # OWNER_PID_LISTENER
        if not groesse.value:
            continue
        buf = ctypes.create_string_buffer(groesse.value)
        if _iphlp.GetExtendedTcpTable(buf, ctypes.byref(groesse), False, familie, 3, 0) != 0:
            continue
        anzahl = struct.unpack_from('<I', buf, 0)[0]
        for i in range(anzahl):
            basis = 4 + i * zeilenlaenge
            if familie == socket.AF_INET:
                _, adr, port, _, _, pid = struct.unpack_from('<IIIIII', buf, basis)
                adresse = socket.inet_ntoa(struct.pack('<I', adr))
            else:
                adresse = socket.inet_ntop(socket.AF_INET6, buf.raw[basis:basis + 16])
                port, = struct.unpack_from('<I', buf, basis + 20)
                pid, = struct.unpack_from('<I', buf, basis + 52)
            out.append((adresse, socket.ntohs(port & 0xFFFF), pid))
    return out


# ---------------------------------------------------------------- Grafikadapter

class _LUID(ctypes.Structure):
    _fields_ = [('LowPart', wt.DWORD), ('HighPart', wt.LONG)]


class _ADAPTERINFO(ctypes.Structure):
    _fields_ = [('hAdapter', ctypes.c_uint), ('AdapterLuid', _LUID),
                ('NumOfSources', wt.ULONG), ('bPrecisePresentRegionsPreferred', wt.BOOL)]


class _ENUMADAPTERS2(ctypes.Structure):
    _fields_ = [('NumAdapters', wt.ULONG), ('pAdapters', ctypes.POINTER(_ADAPTERINFO))]


class _QUERYADAPTERINFO(ctypes.Structure):
    _fields_ = [('hAdapter', ctypes.c_uint), ('Type', ctypes.c_int),
                ('pPrivateDriverData', ctypes.c_void_p), ('PrivateDriverDataSize', ctypes.c_uint)]


class _ADAPTERADDRESS(ctypes.Structure):
    _fields_ = [('BusNumber', ctypes.c_uint), ('DeviceNumber', ctypes.c_uint), ('FunctionNumber', ctypes.c_uint)]


def adapter_pci_busse():
    """{'luid_0x..._0x...': PCI-Busnummer} für alle Windows-Grafikadapter."""
    e = _ENUMADAPTERS2(0, None)
    if _gdi32.D3DKMTEnumAdapters2(ctypes.byref(e)) != 0 or not e.NumAdapters:
        return {}
    feld = (_ADAPTERINFO * e.NumAdapters)()
    e.pAdapters = feld
    if _gdi32.D3DKMTEnumAdapters2(ctypes.byref(e)) != 0:
        return {}
    out = {}
    for a in feld[:e.NumAdapters]:
        adresse = _ADAPTERADDRESS()
        abfrage = _QUERYADAPTERINFO(a.hAdapter, 6, ctypes.cast(ctypes.byref(adresse), ctypes.c_void_p),
                                    ctypes.sizeof(adresse))  # KMTQAITYPE_ADAPTERADDRESS
        if _gdi32.D3DKMTQueryAdapterInfo(ctypes.byref(abfrage)) == 0 and adresse.BusNumber < 0xFFFF:
            luid = f'luid_0x{a.AdapterLuid.HighPart & 0xFFFFFFFF:08x}_0x{a.AdapterLuid.LowPart:08x}'
            out[luid] = adresse.BusNumber
        _gdi32.D3DKMTCloseAdapter(ctypes.byref(ctypes.c_uint(a.hAdapter)))
    return out


class _PDH_WERT(ctypes.Structure):
    _fields_ = [('CStatus', wt.DWORD), ('_ausrichtung', wt.DWORD), ('largeValue', ctypes.c_longlong)]


class _PDH_EINTRAG(ctypes.Structure):
    _fields_ = [('szName', wt.LPWSTR), ('FmtValue', _PDH_WERT)]


class VramJeProzess:
    """Liest den belegten Grafikspeicher je Prozess aus dem Windows-Leistungsindikator."""

    def __init__(self):
        self._abfrage = ctypes.c_void_p()
        self._zaehler = ctypes.c_void_p()
        self.verfuegbar = (
            _pdh.PdhOpenQueryW(None, 0, ctypes.byref(self._abfrage)) == 0 and
            _pdh.PdhAddEnglishCounterW(self._abfrage, '\\GPU Process Memory(*)\\Dedicated Usage', 0,
                                       ctypes.byref(self._zaehler)) == 0)

    def lesen(self):
        """[(pid, luid, bytes)] aller Prozesse mit belegtem Grafikspeicher."""
        if not self.verfuegbar or _pdh.PdhCollectQueryData(self._abfrage) != 0:
            return []
        groesse, anzahl = wt.DWORD(0), wt.DWORD(0)
        _pdh.PdhGetFormattedCounterArrayW(self._zaehler, 0x400, ctypes.byref(groesse), ctypes.byref(anzahl), None)
        if not groesse.value:
            return []
        buf = ctypes.create_string_buffer(groesse.value)
        if _pdh.PdhGetFormattedCounterArrayW(self._zaehler, 0x400, ctypes.byref(groesse),
                                             ctypes.byref(anzahl), buf) != 0:
            return []
        eintraege = ctypes.cast(buf, ctypes.POINTER(_PDH_EINTRAG))
        out = []
        for i in range(anzahl.value):
            teile = (eintraege[i].szName or '').lower().split('_')  # pid_123_luid_0x.._0x.._phys_0
            wert = eintraege[i].FmtValue.largeValue
            if len(teile) >= 5 and teile[0] == 'pid' and wert > 0:
                out.append((int(teile[1]), '_'.join(teile[2:5]), wert))
        return out


# ---------------------------------------------------------------- Fenster

def fenster_schliessen(pids):
    """Sendet WM_CLOSE an alle Top-Level-Fenster dieser PIDs, auch unsichtbare. -> Anzahl."""
    pids = set(pids)
    anzahl = 0

    def schliessen(hwnd, _):
        nonlocal anzahl
        pid = wt.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value in pids and _user32.PostMessageW(hwnd, 0x0010, 0, 0):  # WM_CLOSE
            anzahl += 1
        return True

    _user32.EnumWindows(_WNDENUMPROC(schliessen), 0)
    return anzahl


def fenster_vorholen(pids):
    """Holt das sichtbare Hauptfenster eines der Prozesse in den Vordergrund."""
    treffer = []

    def pruefen(hwnd, _):
        if _user32.IsWindowVisible(hwnd) and _user32.GetWindowTextLengthW(hwnd) > 0 \
                and not _user32.GetWindow(hwnd, 4):  # GW_OWNER: nur Hauptfenster
            pid = wt.DWORD()
            _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                treffer.append(hwnd)
        return True

    _user32.EnumWindows(_WNDENUMPROC(pruefen), 0)
    if not treffer:
        return False
    hwnd = treffer[0]
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, 9)  # SW_RESTORE
    # Windows verweigert Hintergrundprozessen den Fokuswechsel; ein kurzer Alt-Druck hebt die Sperre auf.
    _user32.keybd_event(0x12, 0, 0, 0)
    _user32.keybd_event(0x12, 0, 2, 0)
    return bool(_user32.SetForegroundWindow(hwnd))


# ---------------------------------------------------------------- Prozessgruppe

class _IO_ZAEHLER(ctypes.Structure):
    _fields_ = [(n, ctypes.c_ulonglong) for n in ('r', 'w', 'a', 'rb', 'wb', 'ab')]


class _GRUNDGRENZEN(ctypes.Structure):
    _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                ('LimitFlags', wt.DWORD), ('MinimumWorkingSetSize', ctypes.c_size_t),
                ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', wt.DWORD),
                ('Affinity', ctypes.c_size_t), ('PriorityClass', wt.DWORD), ('SchedulingClass', wt.DWORD)]


class _ERWEITERTE_GRENZEN(ctypes.Structure):
    _fields_ = [('BasicLimitInformation', _GRUNDGRENZEN), ('IoInfo', _IO_ZAEHLER),
                ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]


_k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wt.LPCWSTR]
_k32.CreateJobObjectW.restype = wt.HANDLE
_k32.SetInformationJobObject.argtypes = [wt.HANDLE, ctypes.c_int, ctypes.c_void_p, wt.DWORD]
_k32.AssignProcessToJobObject.argtypes = [wt.HANDLE, wt.HANDLE]
_k32.TerminateJobObject.argtypes = [wt.HANDLE, wt.UINT]
_ntdll.NtResumeProcess.argtypes = [wt.HANDLE]
CREATE_SUSPENDED = 0x00000004


class Prozessgruppe:
    """Startet ein Programm in einer eigenen Windows-Prozessgruppe (Job Object).

    Alle Kindprozesse (Whisper-Worker, ffmpeg) gehören automatisch dazu. `beenden()`
    beendet genau diese Gruppe und nichts sonst. Endet der startende Dienst,
    schließt Windows die Gruppe und beendet sie mit, es bleiben keine Waisen.
    """

    def __init__(self, argv, arbeitsordner, env=None, eingabe=False):
        """`eingabe=True`: Standardeingabe als Rohr, zu füllen mit `prozess.communicate(input=...)`."""
        env = {k: v for k, v in (env if env is not None else os.environ).items()
               if k.upper() not in _GEERBT_NICHT_WEITERGEBEN}
        self.job = _k32.CreateJobObjectW(None, None)
        if not self.job:
            raise OSError('Prozessgruppe konnte nicht angelegt werden.')
        grenzen = _ERWEITERTE_GRENZEN()
        grenzen.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        _k32.SetInformationJobObject(self.job, 9, ctypes.byref(grenzen), ctypes.sizeof(grenzen))
        # Angehalten starten, damit kein Kindprozess vor der Zuordnung zur Gruppe entsteht.
        self.prozess = subprocess.Popen(argv, cwd=arbeitsordner, env=env,
                                        stdin=subprocess.PIPE if eingabe else subprocess.DEVNULL,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        creationflags=CREATE_NO_WINDOW | CREATE_SUSPENDED)
        griff = int(self.prozess._handle)
        if not _k32.AssignProcessToJobObject(self.job, griff):
            self.prozess.kill()
            self.schliessen()
            raise OSError('Prozess konnte der Gruppe nicht zugeordnet werden.')
        _ntdll.NtResumeProcess(griff)

    def beenden(self):
        if self.job:
            _k32.TerminateJobObject(self.job, 1)

    def schliessen(self):
        if self.job:
            _k32.CloseHandle(self.job)
            self.job = None


# ---------------------------------------------------------------- Dateiauswahl

class _OPENFILENAMEW(ctypes.Structure):
    _fields_ = [('lStructSize', wt.DWORD), ('hwndOwner', wt.HWND), ('hInstance', wt.HINSTANCE),
                ('lpstrFilter', ctypes.c_void_p), ('lpstrCustomFilter', wt.LPWSTR), ('nMaxCustFilter', wt.DWORD),
                ('nFilterIndex', wt.DWORD), ('lpstrFile', ctypes.c_void_p), ('nMaxFile', wt.DWORD),
                ('lpstrFileTitle', wt.LPWSTR), ('nMaxFileTitle', wt.DWORD), ('lpstrInitialDir', wt.LPCWSTR),
                ('lpstrTitle', wt.LPCWSTR), ('Flags', wt.DWORD), ('nFileOffset', wt.WORD),
                ('nFileExtension', wt.WORD), ('lpstrDefExt', wt.LPCWSTR), ('lCustData', wt.LPARAM),
                ('lpfnHook', ctypes.c_void_p), ('lpTemplateName', wt.LPCWSTR), ('pvReserved', ctypes.c_void_p),
                ('dwReserved', wt.DWORD), ('FlagsEx', wt.DWORD)]


_comdlg = ctypes.WinDLL('comdlg32')
_comdlg.GetOpenFileNameW.argtypes = [ctypes.POINTER(_OPENFILENAMEW)]
_user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]


def fenster_mit_titel(titel):
    """Sichtbares Hauptfenster mit genau diesem Titel oder None."""
    treffer = []

    def pruefen(hwnd, _):
        n = _user32.GetWindowTextLengthW(hwnd)
        if n and _user32.IsWindowVisible(hwnd) and not _user32.GetWindow(hwnd, 4):
            puffer = ctypes.create_unicode_buffer(n + 1)
            _user32.GetWindowTextW(hwnd, puffer, n + 1)
            if puffer.value == titel:
                treffer.append(hwnd)
        return True

    _user32.EnumWindows(_WNDENUMPROC(pruefen), 0)
    return treffer[0] if treffer else None


def dateien_waehlen(titel, filter_name, endungen, besitzer=None):
    """Windows-Dialog „Öffnen“ mit Mehrfachauswahl. -> Liste vollständiger Pfade (leer bei Abbruch)."""
    muster = ';'.join('*' + e for e in endungen)
    filter_puffer = ctypes.create_unicode_buffer(f'{filter_name}\0{muster}\0Alle Dateien\0*.*\0\0')
    datei_puffer = ctypes.create_unicode_buffer(65536)
    ofn = _OPENFILENAMEW()
    ofn.lStructSize = ctypes.sizeof(ofn)
    ofn.hwndOwner = besitzer
    ofn.lpstrFilter = ctypes.addressof(filter_puffer)
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.addressof(datei_puffer)
    ofn.nMaxFile = len(datei_puffer)
    ofn.lpstrTitle = titel
    # EXPLORER | ALLOWMULTISELECT | FILEMUSTEXIST | PATHMUSTEXIST | NOCHANGEDIR | HIDEREADONLY
    ofn.Flags = 0x80000 | 0x200 | 0x1000 | 0x800 | 0x8 | 0x4
    # Windows lässt Hintergrundprozesse sonst kein Fenster nach vorn holen; ein kurzer Alt-Druck hebt die Sperre auf.
    _user32.keybd_event(0x12, 0, 0, 0)
    _user32.keybd_event(0x12, 0, 2, 0)
    if not _comdlg.GetOpenFileNameW(ctypes.byref(ofn)):
        return []
    teile = []
    for teil in datei_puffer[:].split('\0'):
        if not teil:
            break
        teile.append(teil)
    if len(teile) <= 1:
        return teile
    return [os.path.join(teile[0], t) for t in teile[1:]]


# ---------------------------------------------------------------- Papierkorb

class _SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [('hwnd', wt.HWND), ('wFunc', wt.UINT), ('pFrom', ctypes.c_void_p), ('pTo', ctypes.c_void_p),
                ('fFlags', ctypes.c_ushort), ('fAnyOperationsAborted', wt.BOOL), ('hNameMappings', ctypes.c_void_p),
                ('lpszProgressTitle', wt.LPCWSTR)]


def in_papierkorb(pfade):
    """Legt Dateien in den Papierkorb (rückholbar), ohne Rückfrage und ohne Fenster. -> True bei Erfolg."""
    pfade = [os.path.abspath(p) for p in pfade if p]
    if not pfade:
        return True
    text = '\0'.join(pfade) + '\0\0'
    puffer = (ctypes.c_wchar * len(text))(*text)
    op = _SHFILEOPSTRUCTW()
    op.wFunc = 3  # FO_DELETE
    op.pFrom = ctypes.addressof(puffer)
    # ALLOWUNDO (Papierkorb) | NOCONFIRMATION | SILENT | NOERRORUI
    op.fFlags = 0x40 | 0x10 | 0x4 | 0x400
    ergebnis = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    return ergebnis == 0 and not op.fAnyOperationsAborted
