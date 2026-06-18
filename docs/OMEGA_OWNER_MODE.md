# Omega Owner Mode

Omega Owner Mode is the baseline direction for Xoduz/XV7 on the Omega desktop.

The goal is not a read-only chatbot. The goal is a local operator assistant that can communicate, inspect, write, test, repair, and eventually perform system-administration tasks on the user's own machine through explicit capabilities, receipts, and confirmations.

## Core principle

X should have the capability to operate like a human local operator, but capability must flow through a visible operator broker rather than hidden model guesses.

That means:

- capabilities exist from the start;
- protections are confirmations, receipts, target checks, and mode boundaries;
- protections must not be buried blockers that silently prevent useful work;
- every action should be inspectable and repeatable;
- destructive operations require break-glass confirmation, not permanent removal of the capability.

## Immediate baseline

The first Omega baseline is intentionally focused:

1. Talk to X locally without paid VS Code/Codex credits.
2. Let X inspect Omega and the XV7 repo.
3. Let X write inside the XV7 repo in owner mode.
4. Let X run test/diagnostic commands.
5. Let X produce action receipts.
6. Let X propose and apply patches through an explicit operator path.
7. Let X rerun proof after a patch.

## Mode contract

Omega is the builder. Laptop/field operation is out of scope until the local Omega unit works.

```text
XV7_MACHINE_PROFILE=omega
XV7_OWNER_MODE=1
XV7_OPERATOR_REPO_ROOT=/workspace
XV7_ALLOW_REPO_WRITE=1
XV7_ALLOW_TEST_RUNS=1
XV7_ALLOW_DOCKER_CONTROL=1
XV7_ALLOW_SYSTEM_ADMIN=0
XV7_ALLOW_DESTRUCTIVE_OPS=0
```

The last two flags are deliberately off for the first baseline. They are not philosophical restrictions. They are staged capability gates. The broker should understand those capability classes from day one so they can be enabled later without redesigning the architecture.

## Capability levels

### Level 1: Eyes

Allowed by default in Omega Owner Mode.

- health check
- runtime/model status
- Docker container status
- repo status
- logs
- hardware summary
- disk inventory
- network summary

### Level 2: Developer hands

Allowed by default in Omega Owner Mode.

- write repo files
- apply patches
- run tests
- run lint/build commands
- restart XV7 containers
- edit XV7 config
- create proof receipts

### Level 3: System admin hands

Capability exists, but is disabled in the first baseline.

- install packages
- edit system services
- change firewall/network configuration
- mount/unmount drives
- restart host services

### Level 4: Break-glass destructive operations

Capability exists as a broker class, but is disabled in the first baseline and must later require exact target confirmation.

- wipe drives
- partition/format drives
- delete large trees
- remove Docker volumes
- reset databases
- boot/firmware-level operations

## First success target

X must be able to complete this local loop on Omega:

```text
Otis: X, run doctor.
X: reports health, model status, repo status, write access, test availability.

Otis: X, run tests.
X: runs the configured test command and captures output.

Otis: X, fix the first failure.
X: identifies the first failure, proposes a patch, applies it when approved, reruns proof.
```

## Non-goals for this pass

- laptop/field profile
- secure tunnel
- avatar polish
- new UI polish
- broad memory redesign
- destructive disk operations

Those come after Omega can repair XV7 locally.
