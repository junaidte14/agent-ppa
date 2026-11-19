
# Threat Model — Tool-Using AI Agent

## 1. System Overview

This project implements a tool-using AI agent with:
- LLM-based tool selection
- Tool registry
- Pydantic argument validation
- Permission-based authorization
- Human approval for sensitive actions
- Retry and timeout handling
- SQLite-backed idempotency
- Lease ownership and recovery
- Structured audit logging

## 2. Assets to Protect

- Correctness of tool execution
- User authorization and approval decisions
- Integrity of operation records
- Idempotency keys and execution ownership
- Audit log integrity
- User data and tool outputs

## 3. Trust Boundaries

- User input -> LLM
- LLM -> Tool registry
- Tool registry -> Authorization policy
- Approval callback -> Tool execution
- Tool execution -> External side effects
- Agent -> SQLite operation store
- Tool output -> LLM context

## 4. Potential Threats

- Malformed tool arguments
- Unauthorized tool invocation
- Prompt injection
- Approval bypass attempts
- Duplicate operation execution
- Concurrent execution conflicts
- Expired lease ownership
- Tool execution failures
- Corrupted or unavailable operation storage
- Misleading tool output
- Approval replay or approval applied to modified arguments.
- Idempotency key reuse across different users or operations.
- Resource exhaustion through excessive or expensive tool calls.
- Sensitive data leakage through prompts, errors, logs, or tool outputs.

## 5. Security and Reliability Objectives

- Unauthorized operations must not execute.
- Rejected operations must not execute.
- Duplicate requests must not cause duplicate side effects.
- Expired lease owners must not finalize operations.
- Failures must not be reported as successful execution.
- Untrusted tool output must not override application policies.
- Operation outcomes must be auditable.


## 6. Potential Threat Actors

- Malicious users crafting adversarial requests.
- Users accidentally requesting unintended actions.
- Malicious instructions embedded in retrieved documents or tool outputs.
- Compromised or unreliable external services.
- Concurrent workers attempting to execute the same operation.
- Application failures, crashes, and interrupted execution.

## 7. Additional Assets

- LLM provider API credentials.
- Application configuration and permission policies.
- User-provided documents and conversation data.
- External service credentials and authorization tokens.

## 8. Additional Security Requirements

- External tool outputs must be treated as untrusted data.
- Tool descriptions and system prompts must not be treated as authorization controls.
- Approval must apply to the validated operation being executed.
- Sensitive credentials must not appear in prompts, tool outputs, or audit logs.
- Uncertain external side effects must be reconciled before retrying.
- Audit records should support reconstruction of important execution events.
- Database failures must not silently bypass authorization or operation-state checks.
- Approval must be bound to the exact validated operation, including its tool name and arguments.
- Idempotency keys must be scoped appropriately to prevent cross-user or cross-operation interference.
- Tool execution must enforce reasonable limits on arguments, execution time, and repeated requests.
- Logs and error messages must not expose API keys, credentials, tokens, or unnecessary private data.

## 9. Scope and Limitations

This project currently demonstrates application-level execution controls.

It does not yet provide:
- Complete identity and access management.
- Production-grade secrets management.
- Comprehensive prompt-injection protection.
- Distributed transaction guarantees.
- Guaranteed exactly-once execution across external services.
- Production-grade tamper-resistant audit storage.
