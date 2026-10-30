"""ComfyUI front end for pinned Ideogram 4 base and fal Instant checkpoints."""
import gc
import json
from pathlib import Path
import numpy as np
import torch

_PIPE = None
_MODE = None


class PromptBuilder:
    CATEGORY = 'ACDEV/Ideogram 4'
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('structured_caption',)
    FUNCTION = 'build'

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'scene': ('STRING', {'multiline': True, 'default': 'A charming illustrated fox reads a newspaper at a Paris cafe. Warm late-afternoon light, detailed ink linework.'}),
            'style': ('STRING', {'default': 'Editorial illustration, warm color palette, crisp details'}),
            'text_in_image': ('STRING', {'default': 'THE DAILY FOX'}),
            'background': ('STRING', {'default': 'A quiet cafe terrace with flowers and soft golden light'}),
            'layout': ('STRING', {'multiline': True, 'default': 'Subject in the center. Clear readable headline above the subject. Generous negative space.'}),
            'raw_json': ('STRING', {'multiline': True, 'default': ''}),
        }}

    def build(self, scene, style, text_in_image, background, layout, raw_json):
        if raw_json.strip():
            data = json.loads(raw_json)
            if not isinstance(data, dict) or 'high_level_description' not in data:
                raise ValueError('Structured captions require a JSON object with high_level_description')
        else:
            elements = [{'type': 'object', 'desc': scene}]
            if text_in_image.strip():
                elements.append({'type': 'text', 'text': text_in_image, 'desc': 'Clear, accurately spelled lettering. ' + layout})
            data = {'high_level_description': scene + ' ' + layout,
                    'style': {'description': style},
                    'compositional_deconstruction': {'background': background, 'elements': elements}}
        return (json.dumps(data, ensure_ascii=False),)


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
    from diffusers import Ideogram4Pipeline, Ideogram4Transformer2DModel
    root = Path('/workspace/ComfyUI/models/ideogram')
    if mode == 'base':
        pipe = Ideogram4Pipeline.from_pretrained(str(root / 'base'), torch_dtype=torch.bfloat16, local_files_only=True)
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
                    unconditional_transformer=None, torch_dtype=torch.bfloat16, local_files_only=True)
        pipe.register_modules(unconditional_transformer=ZeroUnconditional())
    pipe.to('cuda')
    _PIPE, _MODE = pipe, mode
    return pipe


class IdeogramStudio:
    CATEGORY = 'ACDEV/Ideogram 4'
    RETURN_TYPES = ('IMAGE',)
    FUNCTION = 'generate'

    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'caption': ('STRING', {'forceInput': True}),
            'mode': (['base', 'distilled'],),
            'width': ('INT', {'default': 1024, 'min': 512, 'max': 2048, 'step': 16}),
            'height': ('INT', {'default': 1024, 'min': 512, 'max': 2048, 'step': 16}),
            'seed': ('INT', {'default': 42, 'min': 0, 'max': 2**63-1, 'control_after_generate': False}),
            'steps': ('INT', {'default': 48, 'min': 1, 'max': 100}),
            'guidance': ('FLOAT', {'default': 7.0, 'min': 1.0, 'max': 15.0, 'step': 0.1}),
            'sampler': (['lcm', 'euler'],),
            'noise_multiplier': ('FLOAT', {'default': 2.0, 'min': 0.1, 'max': 3.0, 'step': 0.1}),
            'schedule_mu': ('FLOAT', {'default': 0.0, 'min': -5.0, 'max': 5.0}),
            'schedule_std': ('FLOAT', {'default': 1.75, 'min': 0.1, 'max': 5.0}),
            'max_text_tokens': ('INT', {'default': 1024, 'min': 256, 'max': 2048, 'step': 128}),
            'edit_strength': ('FLOAT', {'default': 0.5, 'min': 0.0, 'max': 1.0, 'step': 0.05}),
        }, 'optional': {'reference_image': ('IMAGE',)}}

    def generate(self, caption, mode, width, height, seed, steps, guidance, sampler,
                 noise_multiplier, schedule_mu, schedule_std, max_text_tokens, edit_strength=0.5, reference_image=None):
        json.loads(caption)
        if mode == 'distilled' and guidance != 1.0:
            raise ValueError('The distilled single-branch checkpoint requires guidance=1.0')
        pipe = load_pipeline(mode)
        from diffusers import FlowMatchEulerDiscreteScheduler
        from diffusers.schedulers.scheduling_utils import SchedulerOutput
        generator = torch.Generator(device='cuda').manual_seed(seed)
        image_latent = None
        if reference_image is not None:
            import torch.nn.functional as F
            pixels = reference_image[:1, :, :, :3].movedim(-1, 1).to('cuda')
            pixels = F.interpolate(pixels, size=(height, width), mode='bicubic', align_corners=False).clamp(0, 1)
            if edit_strength == 0:
                return (pixels.movedim(1, -1).cpu(),)
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
                image = pipe(caption, width=width, height=height, num_inference_steps=steps,
                    guidance_scale=guidance, guidance_schedule=None, mu=schedule_mu, std=schedule_std,
                    max_sequence_length=max_text_tokens, generator=generator, prompt_upsampling=False).images[0]
        finally:
            pipe.prepare_latents = original
        return (torch.from_numpy(np.asarray(image).astype(np.float32) / 255.0).unsqueeze(0),)


NODE_CLASS_MAPPINGS = {'AcdevIdeogramPrompt': PromptBuilder, 'AcdevIdeogramStudio': IdeogramStudio}
NODE_DISPLAY_NAME_MAPPINGS = {'AcdevIdeogramPrompt': 'Ideogram — Prompt, text and layout', 'AcdevIdeogramStudio': 'Ideogram 4 — Shot settings'}
