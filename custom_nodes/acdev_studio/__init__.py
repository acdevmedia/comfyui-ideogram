"""ComfyUI front end for pinned Ideogram 4 base and fal Instant checkpoints."""
import gc
import json
from pathlib import Path
import numpy as np
import torch

_PIPE = None
_MODE = None

# Official Ideogram 4 presets. The guidance schedule's final low-guidance entries are the
# documented "polish" steps; a constant guidance_scale replaces the whole schedule.
PRESETS = {
    '4.0 Default 20': {'steps': 20, 'schedule': (7.0,) * 18 + (3.0,) * 2, 'mu': 0.0, 'std': 1.75},
    '4.0 Quality 48': {'steps': 48, 'schedule': (7.0,) * 45 + (3.0,) * 3, 'mu': 0.0, 'std': 1.5},
    '4.0 Turbo 12': {'steps': 12, 'schedule': (7.0,) * 11 + (3.0,) * 1, 'mu': 0.5, 'std': 1.75},
}


MEDIUMS = ['photograph', 'illustration', '3d_render', 'painting', 'graphic_design']


def parse_palette(raw, limit):
    """Uppercase #RRGGBB entries, as the caption verifier expects."""
    colors = []
    for chunk in raw.replace(',', ' ').split():
        value = chunk.strip().upper()
        if not value:
            continue
        if not value.startswith('#'):
            value = '#' + value
        if len(value) != 7 or any(c not in '0123456789ABCDEF' for c in value[1:]):
            raise ValueError('Palette colors must be #RRGGBB, got %r' % chunk)
        colors.append(value)
    if len(colors) > limit:
        raise ValueError('At most %d palette colors here, got %d' % (limit, len(colors)))
    return colors


def parse_bbox(raw):
    """[y_min, x_min, y_max, x_max] in normalized 0-1000 coordinates, origin top-left."""
    raw = raw.strip()
    if not raw or raw == '-':
        return None
    parts = [p for p in raw.replace(',', ' ').split() if p]
    if len(parts) != 4:
        raise ValueError('A bbox needs 4 numbers (y_min x_min y_max x_max), got %r' % raw)
    try:
        box = [int(round(float(p))) for p in parts]
    except ValueError:
        raise ValueError('Bbox values must be numbers, got %r' % raw)
    if any(v < 0 or v > 1000 for v in box):
        raise ValueError('Bbox values are 0-1000 normalized coordinates, got %r' % raw)
    if box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError('Bbox must be y_min x_min y_max x_max with y_min<y_max and x_min<x_max, got %r' % raw)
    return box


def parse_elements(raw):
    """One element per line. Bare text is an object; otherwise pipe-separated fields:

    obj  | y,x,y,x | description
    text | y,x,y,x | THE WORDS | description
    """
    elements = []
    for number, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        try:
            if '|' not in line:
                elements.append({'type': 'obj', 'desc': line})
                continue
            fields = [f.strip() for f in line.split('|')]
            kind = fields[0].lower()
            if kind not in ('obj', 'text'):
                raise ValueError('Element type must be obj or text, got %r' % fields[0])
            wanted = 4 if kind == 'text' else 3
            if len(fields) == wanted + 1:
                palette = parse_palette(fields[-1], 5)
                fields = fields[:-1]
            else:
                palette = []
            if len(fields) != wanted:
                raise ValueError('A %s element needs %d fields separated by |' % (kind, wanted))
            bbox = parse_bbox(fields[1])
            # Key order is part of the trained format, so build each dict in order.
            element = {'type': kind}
            if bbox:
                element['bbox'] = bbox
            if kind == 'text':
                element['text'] = fields[2]
                element['desc'] = fields[3]
            else:
                element['desc'] = fields[2]
            if palette:
                element['color_palette'] = palette
            elements.append(element)
        except ValueError as exc:
            raise ValueError('Element line %d: %s' % (number, exc))
    return elements


class PromptBuilder:
    CATEGORY = 'ACDEV/Ideogram 4'
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('structured_caption',)
    FUNCTION = 'build'

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'scene': ('STRING', {'multiline': True, 'default': ''}),
            'background': ('STRING', {'multiline': True, 'default': ''}),
            'elements': ('STRING', {'multiline': True, 'default': ''}),
            'aesthetics': ('STRING', {'default': ''}),
            'lighting': ('STRING', {'default': ''}),
            'medium': ([''] + MEDIUMS,),
            'photo_or_art_style': ('STRING', {'default': ''}),
            'color_palette': ('STRING', {'default': ''}),
            'raw_json': ('STRING', {'multiline': True, 'default': ''}),
        }}

    def build(self, scene, background, elements, aesthetics, lighting, medium,
              photo_or_art_style, color_palette, raw_json):
        if raw_json.strip():
            data = json.loads(raw_json)
            if not isinstance(data, dict) or 'compositional_deconstruction' not in data:
                raise ValueError('A structured caption needs a compositional_deconstruction object')
            return (json.dumps(data, ensure_ascii=False, separators=(',', ':')),)

        if not scene.strip():
            raise ValueError('Describe the scene, or paste a full structured caption into raw_json')
        if not background.strip():
            raise ValueError('Describe the background; the caption schema requires it')

        parsed = parse_elements(elements)
        if not parsed:
            raise ValueError('List at least one element, one per line (see the node tooltip or README)')

        # Top-level order: high_level_description, style_description, compositional_deconstruction.
        data = {'high_level_description': scene.strip()}

        if medium or aesthetics.strip() or lighting.strip() or photo_or_art_style.strip():
            if not (medium and aesthetics.strip() and lighting.strip()):
                raise ValueError('A style needs medium, aesthetics and lighting together, or leave all style fields empty')
            palette = parse_palette(color_palette, 16)
            style = {'aesthetics': aesthetics.strip(), 'lighting': lighting.strip()}
            # Photo captions order the camera description before the medium; art styles after it.
            if medium == 'photograph':
                if photo_or_art_style.strip():
                    style['photo'] = photo_or_art_style.strip()
                style['medium'] = medium
            else:
                style['medium'] = medium
                if photo_or_art_style.strip():
                    style['art_style'] = photo_or_art_style.strip()
            if palette:
                style['color_palette'] = palette
            data['style_description'] = style
        elif color_palette.strip():
            raise ValueError('A color palette belongs to a style; set medium, aesthetics and lighting too')

        data['compositional_deconstruction'] = {'background': background.strip(), 'elements': parsed}
        return (json.dumps(data, ensure_ascii=False, separators=(',', ':')),)


def load_pipeline(mode):
    global _PIPE, _MODE
    if _PIPE is not None and _MODE == mode:
        print('[models] Reusing loaded Ideogram pipeline:', mode, flush=True)
        return _PIPE
    import comfy.model_management
    comfy.model_management.unload_all_models()
    _PIPE = None
    gc.collect()
    torch.cuda.empty_cache()
    from diffusers import Ideogram4Pipeline, Ideogram4PromptEnhancerHead, Ideogram4Transformer2DModel
    root = Path('/workspace/ComfyUI/models/ideogram')
    # Magic Prompt's generative head grafts onto the shared text encoder, so it costs no extra encoder.
    enhancer = None
    if (root / 'prompt_enhancer').exists():
        enhancer = Ideogram4PromptEnhancerHead.from_pretrained(str(root / 'prompt_enhancer'),
                                                               torch_dtype=torch.bfloat16, local_files_only=True)
    if mode == 'base':
        pipe = Ideogram4Pipeline.from_pretrained(str(root / 'base'), torch_dtype=torch.bfloat16,
                                                 prompt_enhancer_head=enhancer, local_files_only=True)
    else:
        transformer = Ideogram4Transformer2DModel.from_pretrained(str(root / 'distilled'), subfolder='transformer', torch_dtype=torch.bfloat16, local_files_only=True)
        class ZeroUnconditional(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.register_buffer('_anchor', torch.empty(0, dtype=torch.bfloat16), persistent=False)
            @property
            def dtype(self): return self._anchor.dtype
            def forward(self, *, hidden_states, **kwargs): return (torch.zeros_like(hidden_states),)
        pipe = Ideogram4Pipeline.from_pretrained(str(root / 'base'), transformer=transformer,
                    unconditional_transformer=None, torch_dtype=torch.bfloat16,
                    prompt_enhancer_head=enhancer, local_files_only=True)
        pipe.register_modules(unconditional_transformer=ZeroUnconditional())
    pipe.to('cuda')
    _PIPE, _MODE = pipe, mode
    return pipe


class IdeogramStudio:
    CATEGORY = 'ACDEV/Ideogram 4'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('image', 'caption_used')
    FUNCTION = 'generate'

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'prompt': ('STRING', {'multiline': True, 'default': ''}),
            # Ideogram 4 is trained only on structured captions; Magic Prompt writes one from plain text.
            'magic_prompt': ('BOOLEAN', {'default': True}),
            'mode': (['base', 'distilled'],),
            'sampler_preset': (['4.0 Default 20', '4.0 Quality 48', '4.0 Turbo 12', 'custom'],),
            'width': ('INT', {'default': 1280, 'min': 256, 'max': 2048, 'step': 16}),
            'height': ('INT', {'default': 720, 'min': 256, 'max': 2048, 'step': 16}),
            'seed': ('INT', {'default': 0, 'min': 0, 'max': 2**63-1, 'control_after_generate': True}),
            'steps': ('INT', {'default': 20, 'min': 1, 'max': 100}),
            'guidance': ('FLOAT', {'default': 7.0, 'min': 1.0, 'max': 15.0, 'step': 0.1}),
            'sampler': (['euler', 'lcm'],),
            'noise_multiplier': ('FLOAT', {'default': 1.0, 'min': 0.1, 'max': 3.0, 'step': 0.1}),
            'schedule_mu': ('FLOAT', {'default': 0.0, 'min': -5.0, 'max': 5.0}),
            'schedule_std': ('FLOAT', {'default': 1.75, 'min': 0.1, 'max': 5.0}),
            'max_text_tokens': ('INT', {'default': 1024, 'min': 256, 'max': 2048, 'step': 128}),
            'edit_strength': ('FLOAT', {'default': 0.5, 'min': 0.0, 'max': 1.0, 'step': 0.05}),
        }, 'optional': {'caption': ('STRING', {'forceInput': True}), 'reference_image': ('IMAGE',)}}

    def generate(self, prompt, magic_prompt, mode, sampler_preset, width, height, seed, steps, guidance, sampler,
                 noise_multiplier, schedule_mu, schedule_std, max_text_tokens, edit_strength=0.5,
                 caption=None, reference_image=None):
        if caption is not None and caption.strip():
            # An advanced graph supplied a structured caption, so send it through unchanged.
            json.loads(caption)
            text, upsample = caption, False
        else:
            if not prompt.strip():
                raise ValueError('Type a prompt, or connect a structured caption to the caption input')
            text, upsample = prompt.strip(), magic_prompt
        preset = PRESETS.get(sampler_preset) if mode == 'base' else None
        if preset:
            # The schedule's length must match the step count, so the preset owns both.
            steps, schedule_mu, schedule_std = preset['steps'], preset['mu'], preset['std']
            guidance_args = {'guidance_scale': None, 'guidance_schedule': list(preset['schedule'])}
        else:
            if mode == 'distilled' and guidance != 1.0:
                raise ValueError('The distilled single-branch checkpoint requires guidance=1.0')
            guidance_args = {'guidance_scale': guidance, 'guidance_schedule': None}
        pipe = load_pipeline(mode)
        if upsample:
            # Run the enhancer ourselves rather than inside the call, so an empty or malformed
            # caption fails loudly here instead of silently rendering a blank frame.
            if getattr(pipe, 'prompt_enhancer_head', None) is None:
                raise ValueError('Magic Prompt needs the prompt_enhancer model; it is missing from this Pod. '
                                 'Switch magic_prompt off, or redeploy so first boot downloads it.')
            written = pipe.upsample_prompt(text, height=height, width=width,
                                           max_new_tokens=max_text_tokens,
                                           generator=torch.Generator(device='cuda').manual_seed(seed),
                                           device=pipe.device)
            written = written[0] if isinstance(written, (list, tuple)) else written
            try:
                parsed = json.loads(written)
                assert isinstance(parsed, dict) and parsed.get('compositional_deconstruction')
            except Exception:
                raise ValueError('Magic Prompt did not return a usable caption for this prompt. '
                                 'Rephrase it, or switch magic_prompt off and use the advanced '
                                 'caption workflow. Returned: %r' % (written[:300],))
            text, upsample = written, False
        from diffusers import FlowMatchEulerDiscreteScheduler
        from diffusers.schedulers.scheduling_utils import SchedulerOutput
        generator = torch.Generator(device='cuda').manual_seed(seed)
        image_latent = None
        if reference_image is not None:
            import torch.nn.functional as F
            pixels = reference_image[:1, :, :, :3].movedim(-1, 1).to('cuda')
            pixels = F.interpolate(pixels, size=(height, width), mode='bicubic', align_corners=False).clamp(0, 1)
            if edit_strength == 0:
                return (pixels.movedim(1, -1).cpu(), text)
            with torch.inference_mode():
                encoded = pipe.vae.encode((pixels * 2 - 1).to(pipe.vae.dtype), return_dict=False)[0].mode()
                batch, channels, latent_h, latent_w = encoded.shape
                patch = pipe.patch_size
                grid_h, grid_w = latent_h // patch, latent_w // patch
                packed = encoded.view(batch, channels, grid_h, patch, grid_w, patch).permute(0, 2, 4, 3, 5, 1).reshape(batch, grid_h * grid_w, channels * patch * patch).float()
                mean = pipe.vae.bn.running_mean.view(1, 1, -1).to(packed)
                std = torch.sqrt(pipe.vae.bn.running_var + pipe.vae.config.batch_norm_eps).view(1, 1, -1).to(packed)
                image_latent = (packed - mean) / std
        class FlowEditEuler(FlowMatchEulerDiscreteScheduler):
            def set_timesteps(self, *args, **kwargs):
                super().set_timesteps(*args, **kwargs)
                if image_latent is not None:
                    skip = min(len(self.timesteps) - 1, int(len(self.timesteps) * (1.0 - edit_strength)))
                    self.timesteps = self.timesteps[skip:]
                    self.sigmas = self.sigmas[skip:]
                    self.num_inference_steps = len(self.timesteps)
        class FlowLCM(FlowEditEuler):
            """LCM denoised prediction plus next-sigma noise, using flow interpolation."""
            def step(self, model_output, timestep, sample, return_dict=True, **kwargs):
                if self.step_index is None: self._init_step_index(timestep)
                sigma = self.sigmas[self.step_index].to(sample.device)
                sigma_next = self.sigmas[self.step_index + 1].to(sample.device)
                denoised = sample.float() - sigma * model_output.float()
                noise = torch.randn(sample.shape, generator=generator, device=sample.device, dtype=sample.dtype)
                result = (1.0 - sigma_next) * denoised + sigma_next * noise
                self._step_index += 1
                return SchedulerOutput(prev_sample=result) if return_dict else (result,)
        cls = FlowLCM if sampler == 'lcm' else FlowEditEuler
        pipe.scheduler = cls.from_config(pipe.scheduler.config)
        original = pipe.prepare_latents
        def scaled_latents(*args, **kwargs):
            noise = original(*args, **kwargs) * noise_multiplier
            if image_latent is None:
                return noise
            sigma = pipe.scheduler.sigmas[0].to(noise)
            return (1 - sigma) * image_latent.to(noise) + sigma * noise
        pipe.prepare_latents = scaled_latents
        try:
            with torch.inference_mode():
                image = pipe(text, width=width, height=height, num_inference_steps=steps,
                    mu=schedule_mu, std=schedule_std, **guidance_args,
                    max_sequence_length=max_text_tokens, generator=generator,
                    prompt_upsampling=upsample).images[0]
        finally:
            pipe.prepare_latents = original
        return (torch.from_numpy(np.asarray(image).astype(np.float32) / 255.0).unsqueeze(0), text)


NODE_CLASS_MAPPINGS = {'AcdevIdeogramPrompt': PromptBuilder, 'AcdevIdeogramStudio': IdeogramStudio}
NODE_DISPLAY_NAME_MAPPINGS = {'AcdevIdeogramPrompt': 'Ideogram — Prompt, text and layout', 'AcdevIdeogramStudio': 'Ideogram 4 — Shot settings'}
