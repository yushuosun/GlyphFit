"""Independent R1 candidate. No imports of torch/vLLM and no model launch.

This is a NEW unified public candidate. Historical 16k workers
remain preserved in prior commits; no historical outputs are rewritten.
"""
from dataclasses import dataclass, asdict
import copy
import inspect

VERSION = 'TELE_LONG_CONTEXT_OUTPUT_RESERVE_R1'


class BudgetRejected(ValueError):
    pass


@dataclass(frozen=True)
class ContextPolicy:
    context_tokens: int = 32768
    requested_output_tokens: int = 32768
    minimum_output_tokens: int = 8192
    overflow_strategy: str = 'reject_preserve_original'

    @property
    def version(self):
        return f'TELE_CONTEXT{self.context_tokens}_OUTPUT_RESERVE{self.minimum_output_tokens}_CAP{self.requested_output_tokens}_R1'

    def validate(self, model_config):
        for n in (self.context_tokens, self.requested_output_tokens, self.minimum_output_tokens):
            if type(n) is not int or n <= 0:
                raise BudgetRejected('POSITIVE_INTEGER_TOKEN_BUDGET_REQUIRED')
        text = model_config.get('text_config', model_config)
        bounds = [c['max_position_embeddings'] for c in (model_config, text)
                  if 'max_position_embeddings' in c]
        if not bounds or self.context_tokens > min(bounds):
            raise BudgetRejected('EXCEEDS_MODEL_DECLARED_CONTEXT')
        if self.minimum_output_tokens > min(self.requested_output_tokens, self.context_tokens):
            raise BudgetRejected('OUTPUT_FLOOR_EXCEEDS_CAP')
        if self.overflow_strategy != 'reject_preserve_original':
            raise BudgetRejected('CROP_SCALE_OR_TOKEN_TRUNCATION_FORBIDDEN')
        return self

    def budget(self, actual_prompt_tokens):
        if type(actual_prompt_tokens) is not int or actual_prompt_tokens < 1:
            raise BudgetRejected('ACTUAL_MULTIMODAL_PROMPT_COUNT_REQUIRED')
        remaining = self.context_tokens - actual_prompt_tokens
        effective = min(self.requested_output_tokens, remaining)
        if effective < self.minimum_output_tokens:
            raise BudgetRejected('INSUFFICIENT_OUTPUT_RESERVE_PRESERVE_ORIGINAL')
        return dict(version=self.version, prompt_tokens=actual_prompt_tokens,
                    total_context_tokens=self.context_tokens,
                    requested_output_tokens=self.requested_output_tokens,
                    effective_output_tokens=effective,
                    minimum_output_tokens=self.minimum_output_tokens,
                    count_basis='V1_EngineCoreRequest.prompt_token_ids_after_multimodal_expansion',
                    overflow_strategy=self.overflow_strategy)


def configure_new_tele(config_module, policy, model_config):
    """Call before a NEW Tele client/engine factory, never on an existing model."""
    policy.validate(model_config)
    config_module.MAX_MODEL_LEN = policy.context_tokens
    return dict(version=policy.version, **asdict(policy), rope_override=None,
                processor_resize_override=None)


def install_output_reserve(llm, policy, model_config, observe):
    """Gate the processed V1 request before LLMEngine queues it.

    Count expanded image tokens, not tokenizer.encode(chat) or image area.
    The caller retains every resource, asset, seed, sampling and input guard.
    Return an uninstaller for this fresh instance only.
    """
    policy.validate(model_config)
    engine = llm.llm_engine
    if engine.model_config.max_model_len != policy.context_tokens:
        raise BudgetRejected('ACTUAL_ENGINE_CONTEXT_MISMATCH')
    processor = engine.processor
    if getattr(processor, '_long_context_r1_bound', False):
        raise BudgetRejected('ALREADY_BOUND')
    original = processor.process_inputs
    signature = inspect.signature(original)

    def guarded(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        params = bound.arguments['params']
        if getattr(params, 'n', 1) != 1:
            raise BudgetRejected('SINGLE_OUTPUT_REQUIRED_NO_FANOUT')
        if getattr(params, 'truncate_prompt_tokens', None) is not None:
            raise BudgetRejected('PROMPT_TRUNCATION_FORBIDDEN')
        token_options = bound.arguments.get('tokenization_kwargs') or {}
        if token_options.get('truncation') or token_options.get('max_length') is not None:
            raise BudgetRejected('TOKENIZER_TRUNCATION_FORBIDDEN')
        if getattr(params, 'max_tokens', None) != policy.requested_output_tokens:
            raise BudgetRejected('ACTUAL_SAMPLER_OUTPUT_CAP_MISMATCH')
        result = original(*args, **kwargs)
        if not isinstance(result, tuple) or len(result) != 2:
            raise BudgetRejected('VLLM_V1_PROCESSOR_API_MISMATCH')
        text, request = result
        ids = request.prompt_token_ids
        if ids is None or getattr(request, 'prompt_embeds', None) is not None:
            raise BudgetRejected('TOKEN_IDS_REQUIRED_EMBED_COUNT_UNKNOWN')
        record = policy.budget(len(ids))
        if request.sampling_params is None:
            raise BudgetRejected('SAMPLING_REQUEST_REQUIRED')
        # Preserve all original penalties, EOS, stop and plugin parameters.
        # Do not mutate the shared caller SamplingParams object.
        effective = copy.copy(request.sampling_params)
        effective.max_tokens = record['effective_output_tokens']
        request.sampling_params = effective
        observe(dict(record, request_id=request.request_id,
                     queued=False, gate_location='before_LLMEngine.engine_core.add_request'))
        return text, request

    processor.process_inputs = guarded
    processor._long_context_r1_bound = True

    def uninstall():
        if processor.process_inputs is not guarded:
            raise BudgetRejected('INSTANCE_HOOK_CHANGED')
        processor.process_inputs = original
        processor._long_context_r1_bound = False
    return uninstall


def kv_cache_estimate(model_config, tokens, concurrent_sequences=1, dtype_bytes=2):
    """Full attention BF16 K+V only. Not total VRAM or GPU minimum."""
    c = model_config.get('text_config', model_config)
    n = c['num_hidden_layers'] * 2 * c['num_key_value_heads'] * c['head_dim'] * dtype_bytes
    return dict(bytes_per_token=n, tokens=tokens, concurrent_sequences=concurrent_sequences,
                kv_bytes=n*tokens*concurrent_sequences,
                kv_GiB=n*tokens*concurrent_sequences/(1024**3),
                total_VRAM_bytes=None, minimum_card_VRAM_bytes=None,
                excluded='weights, vision encoder, prefill activations, graphs, allocator, fragmentation')
