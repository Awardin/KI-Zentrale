"""Test A (PLAN.md, vorgemerkt 30.10.2026): Open-H3-Regenerate-2K – Studio-Video 960×544 auf 1920×1088.

Bildweg statt Latent-Hochskalierer (der H3-3D-Conv-Hochskalierer hat in ComfyUI 0.37 keinen Kernlader):
Bilder lanczos ×2 → H3-VAE kodieren → mit σ 0,909375 verrauschen → 3 Euler-Schritte (0,909375 → 0,857143 → 0,666667 → 0),
CFG 1, ref2va INT8 + umgerechnete Refiner-LoRA (mit Sharp-Zweigen). Ton: Originalton als Führung (bleibt fest).
Prozess 1 (8188): Modell auf der FE (gpu:0), Text-Encoder und VAE auf der Suprim (gpu:1). Anmeldung bei der Zentrale.
"""
import json, sys
sys.path.insert(0, r'C:\Users\sasch\AppData\Local\Temp\claude\ff062970fa60b2ed\f04aac5f-3869-4c07-9508-f7b5050384e3\scratchpad')
import vae_messung as m  # noqa: E402

V = m.CFG['video']
MD = V['modelle']
QUELLE = sys.argv[1] if len(sys.argv) > 1 else 'Werkstatt-Abnahme/Video-Real-B-n11_00001_.mp4'
NAME = sys.argv[2] if len(sys.argv) > 2 else 'Real-B-n11'
LORA = 'open_h3_regenerate_2k_comfy_bf16.safetensors'
B, H, L = 1920, 1088, 124
begleit = json.load(open(r'C:\Workstation\Arbeitsmaterial\Studio\\' + QUELLE.replace('/', '\\') + '.json', encoding='utf-8'))
PROMPT = begleit['prompt']


def graph(praefix):
    return {
        '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': MD['ref2va'], 'weight_dtype': 'default'}},
        '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': MD['clip'], 'type': 'minimax', 'device': 'default'}},
        '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': MD['vae_video']}},
        '4': {'class_type': 'VAELoader', 'inputs': {'vae_name': MD['vae_audio']}},
        '34': {'class_type': 'VAELoader', 'inputs': {'vae_name': V['dekoder']['int8_v1']['datei']}},
        '20': {'class_type': 'SelectModelDevice', 'inputs': {'model': ['1', 0], 'device': 'gpu:0'}},
        '21': {'class_type': 'SelectCLIPDevice', 'inputs': {'clip': ['2', 0], 'device': 'gpu:1'}},
        '22': {'class_type': 'SelectVAEDevice', 'inputs': {'vae': ['3', 0], 'device': 'gpu:1'}},
        '23': {'class_type': 'SelectVAEDevice', 'inputs': {'vae': ['4', 0], 'device': 'gpu:1'}},
        '35': {'class_type': 'SelectVAEDevice', 'inputs': {'vae': ['34', 0], 'device': 'gpu:1'}},
        '24': {'class_type': 'LoraLoaderModelOnly', 'inputs': {'model': ['20', 0], 'lora_name': LORA, 'strength_model': 1.0}},
        '29': {'class_type': 'ModelAttentionBackend', 'inputs': {'model': ['24', 0], 'attention': 'comfy kitchen attention'}},
        '40': {'class_type': 'LoadVideo', 'inputs': {'file': QUELLE + ' [output]'}},
        '41': {'class_type': 'GetVideoComponents', 'inputs': {'video': ['40', 0]}},
        '42': {'class_type': 'ImageScale', 'inputs': {'image': ['41', 0], 'upscale_method': 'lanczos', 'width': B,
                                                      'height': H, 'crop': 'disabled'}},
        '43': {'class_type': 'VAEEncode', 'inputs': {'pixels': ['42', 0], 'vae': ['22', 0]}},
        '5': {'class_type': 'MiniMaxH3ImageToVideo', 'inputs': {'clip': ['21', 0], 'vae': ['22', 0], 'prompt': PROMPT,
                                                               'width': B, 'height': H, 'length': L}},
        '44': {'class_type': 'LTXVSeparateAVLatent', 'inputs': {'av_latent': ['5', 1]}},
        '45': {'class_type': 'LTXVConcatAVLatent', 'inputs': {'video_latent': ['43', 0], 'audio_latent': ['44', 1]}},
        '50': {'class_type': 'MiniMaxH3AddGuide', 'inputs': {'positive': ['5', 0], 'latent': ['45', 0], 'frame_idx': 0,
                                                             'audio_vae': ['23', 0], 'audio': ['41', 1]}},
        '9': {'class_type': 'KSamplerSelect', 'inputs': {'sampler_name': 'euler'}},
        '10': {'class_type': 'ManualSigmas', 'inputs': {'sigmas': '0.909375, 0.857143, 0.666667, 0.0'}},
        '11': {'class_type': 'BasicGuider', 'inputs': {'model': ['29', 0], 'conditioning': ['50', 0]}},
        '12': {'class_type': 'RandomNoise', 'inputs': {'noise_seed': 4711}},
        '13': {'class_type': 'SamplerCustomAdvanced', 'inputs': {'noise': ['12', 0], 'guider': ['11', 0], 'sampler': ['9', 0],
                                                                 'sigmas': ['10', 0], 'latent_image': ['45', 0]}},
        '14': {'class_type': 'VAEDecode', 'inputs': {'samples': ['13', 0], 'vae': ['35', 0]}},
        '15': {'class_type': 'VAEDecodeAudio', 'inputs': {'samples': ['13', 0], 'vae': ['23', 0]}},
        '16': {'class_type': 'CreateVideo', 'inputs': {'images': ['14', 0], 'audio': ['15', 0], 'fps': float(V['fps'])}},
        '17': {'class_type': 'SaveVideo', 'inputs': {'video': ['16', 0], 'filename_prefix': praefix,
                                                     'format': 'auto', 'codec': 'auto'}},
    }


def f():
    return m.ausfuehren(8188, graph(f'Hochskalieren-Test/{NAME}-1080p'), f'A {NAME} 1080p')


try:
    m.post(8189, '/free', {'unload_models': True, 'free_memory': True})
    erg = m.mit_anmeldung({0: 22528, 1: 20480}, 'bild-video', f'Test A Hochskalieren {NAME}', f, 8188)
finally:
    m.post(8188, '/free', {'unload_models': True, 'free_memory': True})
json.dump(m.ERG, open(sys.argv[0].replace('.py', f'_{NAME}.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
