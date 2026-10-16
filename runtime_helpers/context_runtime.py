"""General fresh-engine 32k integration; no roster, owner or cluster entry."""
import os
import json
from pathlib import Path
from context_budget import ContextPolicy, BudgetRejected, install_output_reserve


def validate_attention_environment(environment):
    if 'VLLM_ATTENTION_BACKEND' in environment:
        raise BudgetRejected('DEFAULT_ATTENTION_SELECTOR_REQUIRED_NO_OVERRIDE')


def scalar(value):
    if hasattr(value, 'value'):
        return scalar(value.value)
    if isinstance(value, (list, tuple)):
        return [scalar(v) for v in value]
    return value


def output_gate_offset(path):
    """Exclude earlier calls' gates from the current generate binding."""
    try:
        return Path(path).stat().st_size
    except FileNotFoundError:
        return 0
    except OSError as error:
        raise BudgetRejected('OUTPUT_GATE_LOG_UNREADABLE') from error


def validate_returned_outputs(outputs, requested_count, contract, path, offset):
    """Run only AFTER every returned raw output has been durably appended."""
    try:
        with Path(path).open('rb') as stream:
            if stream.seek(0, 2) < offset:
                raise BudgetRejected('OUTPUT_GATE_LOG_TRUNCATED_RETAIN_RAW_STOP')
            stream.seek(offset)
            gates = [json.loads(line) for line in stream if line.strip()]
    except (OSError, ValueError, UnicodeError) as error:
        if isinstance(error, BudgetRejected):
            raise
        raise BudgetRejected('OUTPUT_GATE_LOG_INVALID_OR_MISSING_RETAIN_RAW_STOP') from error
    if len(outputs) != requested_count or len(gates) != requested_count:
        raise BudgetRejected('OUTPUT_REQUEST_OR_GATE_CARDINALITY_MISMATCH_RETAIN_RAW_STOP')
    policy = ContextPolicy(**contract['context_policy'])
    if policy.context_tokens != contract['max_model_len']:
        raise BudgetRejected('OUTPUT_CONTRACT_CONTEXT_MISMATCH_RETAIN_RAW_STOP')
    by_id = {}
    for gate in gates:
        request_id = gate.get('request_id') if isinstance(gate, dict) else None
        if not isinstance(request_id, str) or not request_id or request_id in by_id:
            raise BudgetRejected('OUTPUT_GATE_ID_MISSING_OR_DUPLICATE_RETAIN_RAW_STOP')
        by_id[request_id] = gate
    returned_ids = set()
    for output in outputs:
        request_id = getattr(output, 'request_id', None)
        if not isinstance(request_id, str) or request_id not in by_id or request_id in returned_ids:
            raise BudgetRejected('OUTPUT_REQUEST_ID_OR_GATE_MISMATCH_RETAIN_RAW_STOP')
        returned_ids.add(request_id)
        gate = by_id[request_id]
        ids = getattr(output, 'prompt_token_ids', None)
        if ids is None or len(ids) != gate.get('prompt_tokens'):
            raise BudgetRejected('OUTPUT_PROMPT_COUNT_GATE_MISMATCH_RETAIN_RAW_STOP')
        effective = gate.get('effective_output_tokens')
        if type(effective) is not int or effective <= 0 or len(output.outputs) != 1:
            raise BudgetRejected('OUTPUT_EFFECTIVE_BUDGET_OR_CHOICE_INVALID_RETAIN_RAW_STOP')
        output_tokens = len(output.outputs[0].token_ids)
        if output_tokens > effective:
            raise BudgetRejected('OUTPUT_EXCEEDS_EFFECTIVE_BUDGET_RETAIN_RAW_STOP')
        if len(ids) + output_tokens > policy.context_tokens:
            raise BudgetRejected('OUTPUT_EXCEEDS_TOTAL_CONTEXT_RETAIN_RAW_STOP')
        expected = policy.budget(len(ids))
        if any(gate.get(key) != value for key, value in expected.items()) or \
                gate.get('queued') is not False or \
                gate.get('gate_location') != 'before_LLMEngine.engine_core.add_request':
            raise BudgetRejected('OUTPUT_GATE_POLICY_MISMATCH_RETAIN_RAW_STOP')


def bind_fresh_engine(llm, contract, model_config, observe, record_runtime):
    validate_attention_environment(os.environ)
    policy = ContextPolicy(**contract['context_policy']).validate(model_config)
    cfg = llm.llm_engine.vllm_config
    m, c, s, compilation = cfg.model_config, cfg.cache_config, cfg.scheduler_config, cfg.compilation_config
    actual = dict(enforce_eager=m.enforce_eager, seed=m.seed, max_model_len=m.max_model_len,
        gpu_memory_utilization=c.gpu_memory_utilization, enable_prefix_caching=c.enable_prefix_caching,
        max_num_batched_tokens=s.max_num_batched_tokens, enable_chunked_prefill=s.enable_chunked_prefill,
        compilation_level=scalar(compilation.level), cudagraph_mode=scalar(compilation.cudagraph_mode),
        cudagraph_capture_sizes=scalar(compilation.cudagraph_capture_sizes), max_capture_size=compilation.max_capture_size,
        use_inductor=compilation.use_inductor, custom_ops=scalar(compilation.custom_ops), splitting_ops=scalar(compilation.splitting_ops))
    if actual != contract['required_actual_engine']:
        raise BudgetRejected('FROZEN_32K_ENGINE_CONFIGURATION_CHANGED')
    if llm.llm_engine.has_unfinished_requests():
        raise BudgetRejected('NEW_IDLE_ENGINE_REQUIRED')
    record_runtime({'actual': actual, 'actual_max_num_seqs': s.max_num_seqs,
                    'historical_max_num_seqs': None, 'policy': contract['context_policy']})
    return install_output_reserve(llm, policy, model_config, observe)
