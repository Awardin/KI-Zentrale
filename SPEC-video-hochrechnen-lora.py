"""Open-H3-Regenerate-2K-LoRA (Diffusers-Aufbau) in ComfyUIs H3-Aufbau umrechnen (Test A, 05.11.2026).

ComfyUI (Single-File-Aufbau, wie Comfy-Org): attn.qkv_proj = [q; k; v] gestapelt, mlp.fc1 = [gate; value],
blocks.N / token_refiner.blocks.N. Diffusers: getrennte to_q/to_k/to_v, ff.net.0.proj = [value; gate]
(belegt in diffusers/loaders/single_file_utils.py, convert_minimax_h3_*).
- q/k/v: A = [A_q; A_k; A_v], B = Blockdiagonale (Delta exakt gleich)
- fc1: Zeilen von B in den Hälften getauscht
- Sharp-Zweige: curve_A/curve_B auf adaln_proj.linear (Eingang ist dort die 8-D-Kurve, apply_silu aus)
Ausgabe bf16 (Faktoren), Schlüssel diffusion_model.*. Prüft je Modultyp das Delta gegen fp32.
"""
import sys, torch
from safetensors import safe_open
from safetensors.torch import save_file

M = r'C:\Users\sasch\Documents\Codex\2026-09-15\ek\outputs\Lokale-LLM\ComfyUI\models'
QUELLE = M + r'\loras\open_h3_regenerate_2k_lora.safetensors'
KURVE = M + r'\open_h3_regenerate\sharp_curve_branches.safetensors'
ZIEL = M + r'\loras\open_h3_regenerate_2k_comfy_bf16.safetensors'
DT = torch.bfloat16

aus, pruef = {}, {}
with safe_open(QUELLE, 'pt') as f:
    keys = set(f.keys())
    mods = sorted({k.rsplit('.lora_', 1)[0] for k in keys})
    def ab(m):
        return f.get_tensor(m + '.lora_A.weight'), f.get_tensor(m + '.lora_B.weight')
    bloecke = sorted({m.rsplit('.attn.', 1)[0].rsplit('.ff.', 1)[0] for m in mods})
    for b in bloecke:
        ziel = b.replace('transformer.token_refiner.refiner_blocks.', 'token_refiner.blocks.') \
                .replace('transformer.transformer_blocks.', 'blocks.')
        z = 'diffusion_model.' + ziel
        (aq, bq), (ak, bk), (av, bv) = ab(b + '.attn.to_q'), ab(b + '.attn.to_k'), ab(b + '.attn.to_v')
        A = torch.cat([aq, ak, av], 0)
        B = torch.block_diag(bq, bk, bv)
        aus[z + '.attn.qkv_proj.lora_A.weight'], aus[z + '.attn.qkv_proj.lora_B.weight'] = A.to(DT), B.to(DT)
        a, bb = ab(b + '.attn.to_out.0')
        aus[z + '.attn.out_proj.lora_A.weight'], aus[z + '.attn.out_proj.lora_B.weight'] = a.to(DT), bb.to(DT)
        a, bb = ab(b + '.ff.net.0.proj')
        h = bb.shape[0] // 2
        bb2 = torch.cat([bb[h:], bb[:h]], 0)  # [value; gate] -> [gate; value]
        aus[z + '.mlp.fc1.lora_A.weight'], aus[z + '.mlp.fc1.lora_B.weight'] = a.to(DT), bb2.to(DT)
        a2, b2 = ab(b + '.ff.net.2')
        aus[z + '.mlp.fc2.lora_A.weight'], aus[z + '.mlp.fc2.lora_B.weight'] = a2.to(DT), b2.to(DT)
        if b.endswith('transformer_blocks.0') or b.endswith('refiner_blocks.0'):
            # Prüfung: Delta der umgerechneten bf16-Faktoren gegen das Original in fp32
            ref = torch.cat([bq @ aq, bk @ ak, bv @ av], 0)
            neu = aus[z + '.attn.qkv_proj.lora_B.weight'].float() @ aus[z + '.attn.qkv_proj.lora_A.weight'].float()
            pruef[ziel + ' qkv'] = float((neu - ref).norm() / ref.norm())
            ref = bb @ a; ref = torch.cat([ref[h:], ref[:h]], 0)
            neu = aus[z + '.mlp.fc1.lora_B.weight'].float() @ aus[z + '.mlp.fc1.lora_A.weight'].float()
            pruef[ziel + ' fc1'] = float((neu - ref).norm() / ref.norm())
        print(ziel, flush=True)
n_lora = len(aus)
if '--ohne-kurve' not in sys.argv:
    with safe_open(KURVE, 'pt') as f:
        for k in f.keys():
            if k.endswith('.curve_A.weight'):
                m = k[:-len('.curve_A.weight')]
                ziel = m.replace('transformer.transformer_blocks.', 'blocks.')
                aus['diffusion_model.' + ziel + '.lora_A.weight'] = f.get_tensor(k).to(DT)
                aus['diffusion_model.' + ziel + '.lora_B.weight'] = f.get_tensor(m + '.curve_B.weight').to(DT)
print('Module LoRA', n_lora // 2, 'Kurvenzweige', (len(aus) - n_lora) // 2)
print('Prüfung (relativer Fehler bf16):', pruef)
save_file(aus, ZIEL, metadata={'format': 'lora', 'quelle': 'open_h3_regenerate_2k_lora + sharp_curve_branches',
                               'umgerechnet': 'Diffusers -> ComfyUI H3 (qkv blockdiag, fc1 getauscht), bf16'})
print('geschrieben', ZIEL)
