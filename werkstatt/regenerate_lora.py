"""Open-H3-Regenerate-2K: Diffusers-LoRA in ComfyUIs H3-Aufbau umrechnen.

qkv: A vertikal stapeln, B als Blockdiagonale; fc1: B-Hälften von
[value; gate] nach [gate; value] tauschen. Sharp-Zweige curve_A/curve_B
werden zu LoRA-Faktoren auf adaln_proj.linear (8-D-Kurve, ohne SiLU).
Alle 52 × 4 Module und 50 Sharp-Zweige werden gegen den Modellheader
und ihr fp32-Delta geprüft (bf16-Fehler endlich und strikt < 0,2 %).

Separates Werkzeug im ComfyUI-venv, niemals von der Werkstatt aufgerufen.
Import und reine Prüflogik brauchen weder torch noch safetensors.
"""
import argparse
import hashlib
import json
import math
import os
import struct
import tempfile


def modell_header(pfad):
    """Nur den safetensors-Header lesen, keine Modellgewichte laden."""
    with open(pfad, 'rb') as f:
        laenge = struct.unpack('<Q', f.read(8))[0]
        if not 2 <= laenge <= 100 * 1024 * 1024:
            raise ValueError('Ungültiger Modellheader.')
        return json.loads(f.read(laenge))


def erwartete_module():
    bloecke = [f'blocks.{i}' for i in range(50)] + [f'token_refiner.blocks.{i}' for i in range(2)]
    return {f'diffusion_model.{b}.{ziel}' for b in bloecke
            for ziel in ('attn.qkv_proj', 'attn.out_proj', 'mlp.fc1', 'mlp.fc2')} | {
                f'diffusion_model.blocks.{i}.adaln_proj.linear' for i in range(50)}


def pruefen(formen, header, fehler, erwartet=None):
    """Reine verbindliche Prüfung aller Module, Faktoren, Zielgewichte und Delta-Fehler."""
    erwartet = erwartete_module() if erwartet is None else set(erwartet)
    keys = {m + endung for m in erwartet for endung in ('.lora_A.weight', '.lora_B.weight')}
    if set(formen) != keys or set(fehler) != erwartet:
        raise ValueError('Module fehlen oder sind unerwartet (52 × 4 Ziele und 50 Kurvenzweige erforderlich).')
    for m in sorted(erwartet):
        a, b = formen[m + '.lora_A.weight'], formen[m + '.lora_B.weight']
        ziel = m.removeprefix('diffusion_model.') + '.weight'
        # Comfy-Org-Dateien können den diffusion_model-Präfix bereits tragen.
        gew = header.get(ziel) or header.get('diffusion_model.' + ziel)
        if not gew or len(a) != 2 or len(b) != 2 or min(*a, *b) <= 0 \
                or a[0] != b[1] or list(gew.get('shape', [])) != [b[0], a[1]]:
            raise ValueError('Zielschlüssel oder Form stimmt nicht: ' + m)
        delta = fehler[m]
        if not isinstance(delta, (int, float)) or not math.isfinite(delta) or not 0 <= delta < 0.002:
            raise ValueError('Delta-Fehler muss endlich und kleiner als 0,2 % sein: ' + m)


def delta_fehler(a, b, referenz):
    """bf16- gegen fp32-Delta, zeilenweise begrenzt statt riesiger Vollmatrizen."""
    import torch
    norm, diff = 0.0, 0.0
    af = a.float()
    for start in range(0, b.shape[0], 128):
        ende = min(start + 128, b.shape[0])
        ref = referenz(start, ende)
        neu = b[start:ende].float() @ af
        norm += float(torch.sum(ref.double().square()))
        diff += float(torch.sum((neu - ref).double().square()))
    return math.sqrt(diff / norm) if norm else (0.0 if diff == 0 else float('inf'))


def umrechnen(quelle, kurve, ziel, modell):
    import torch
    from safetensors import safe_open
    from safetensors.torch import save_file

    header = modell_header(modell)
    aus, fehler = {}, {}
    def speichern(m, a, b, referenz=None):
        if a.ndim != 2 or b.ndim != 2 or a.shape[0] != b.shape[1]:
            raise ValueError('Ungültige Ausgangsfaktoren: ' + m)
        aa, bb = a.to(torch.bfloat16), b.to(torch.bfloat16)
        if referenz is None:
            referenz = lambda start, ende: b[start:ende].float() @ a.float()
        fehler[m] = delta_fehler(aa, bb, referenz)
        if not math.isfinite(fehler[m]) or fehler[m] >= 0.002:
            raise ValueError(f'Delta-Fehler zu groß: {m}: {fehler[m]}')
        aus[m + '.lora_A.weight'], aus[m + '.lora_B.weight'] = aa, bb

    with safe_open(quelle, framework='pt', device='cpu') as f:
        bloecke = [f'transformer.transformer_blocks.{i}' for i in range(50)] + [
            f'transformer.token_refiner.refiner_blocks.{i}' for i in range(2)]
        erwartet = {b + '.' + m + end for b in bloecke for m in
                    ('attn.to_q', 'attn.to_k', 'attn.to_v', 'attn.to_out.0', 'ff.net.0.proj', 'ff.net.2')
                    for end in ('.lora_A.weight', '.lora_B.weight')}
        if set(f.keys()) != erwartet:
            raise ValueError('Die Quell-LoRA enthält fehlende oder unerwartete Module.')
        def ab(m):
            return f.get_tensor(m + '.lora_A.weight').float(), f.get_tensor(m + '.lora_B.weight').float()
        for block in bloecke:
            m = 'diffusion_model.' + block.replace('transformer.token_refiner.refiner_blocks.',
                'token_refiner.blocks.').replace('transformer.transformer_blocks.', 'blocks.')
            paare = [ab(block + '.attn.to_' + k) for k in ('q', 'k', 'v')]
            a = torch.cat([a for a, b in paare], 0)
            b = torch.block_diag(*[b for a, b in paare])
            def qkv(start, ende):
                teile, offset = [], 0
                for aq, bq in paare:
                    von, bis = max(start - offset, 0), min(ende - offset, bq.shape[0])
                    if bis > von:
                        teile.append(bq[von:bis] @ aq)
                    offset += bq.shape[0]
                return torch.cat(teile, 0)
            speichern(m + '.attn.qkv_proj', a, b, qkv)
            speichern(m + '.attn.out_proj', *ab(block + '.attn.to_out.0'))
            a, b = ab(block + '.ff.net.0.proj')
            if b.shape[0] % 2:
                raise ValueError('fc1 hat keine zwei gleichen Hälften: ' + block)
            halb = b.shape[0] // 2
            b = torch.cat([b[halb:], b[:halb]], 0)
            speichern(m + '.mlp.fc1', a, b)
            speichern(m + '.mlp.fc2', *ab(block + '.ff.net.2'))
            print(m, flush=True)
    with safe_open(kurve, framework='pt', device='cpu') as f:
        erwartet = {f'transformer.transformer_blocks.{i}.adaln_proj.linear.curve_{ab}.weight'
                    for i in range(50) for ab in ('A', 'B')}
        if set(f.keys()) != erwartet:
            raise ValueError('Die 50 Sharp-Zweige fehlen oder haben unerwartete Schlüssel.')
        for i in range(50):
            basis = f'transformer.transformer_blocks.{i}.adaln_proj.linear'
            a, b = (f.get_tensor(basis + '.curve_' + k + '.weight').float() for k in ('A', 'B'))
            if a.shape[1] != 8:
                raise ValueError('Sharp-Zweig erwartet eine 8-D-Kurve.')
            speichern(f'diffusion_model.blocks.{i}.adaln_proj.linear', a, b)
    pruefen({k: list(t.shape) for k, t in aus.items()}, header, fehler)
    # Erst nach allen Prüfungen eine Datei erzeugen; bei Fehlern bleibt auch ein bestehendes Ziel erhalten.
    fd, tmp = tempfile.mkstemp(prefix='.regenerate-', suffix='.safetensors', dir=os.path.dirname(os.path.abspath(ziel)))
    os.close(fd)
    try:
        save_file(aus, tmp, metadata={'format': 'lora',
            'quelle': 'open_h3_regenerate_2k_lora + sharp_curve_branches',
            'umgerechnet': 'Diffusers -> ComfyUI H3 (qkv blockdiag, fc1 getauscht), bf16'})
        sha = hashlib.sha256()
        with open(tmp, 'rb') as f:
            for teil in iter(lambda: f.read(1 << 20), b''):
                sha.update(teil)
        os.replace(tmp, ziel)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    print('SHA-256:', sha.hexdigest())
    print('Module geprüft:', len(fehler), 'maximaler relativer Fehler:', max(fehler.values()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('quelle', 'kurve', 'ziel', 'modell'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    umrechnen(args.quelle, args.kurve, args.ziel, args.modell)


if __name__ == '__main__':
    main()
