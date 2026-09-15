# GWS-0008. Single-instance enforcement

**Tags:** #process

## User Story

As an operator starting the service, I want a second launch to replace the running
instance instead of failing or running alongside it, so that I never end up with two
instances silently competing.

## Behavior

Starting a second instance replaces the running one. The new instance always
continues startup.

## Implementation

- Read the pidfile.
- Ignore missing, invalid, or foreign PIDs.
- Send `SIGTERM` to the existing instance.
- Wait up to 5 seconds for exit.
- Continue startup regardless.

The existing instance exits on `SIGTERM`.

## Testing

### Human

- Start two instances. The first exits, the second keeps running.
- Verify the pidfile contains the second instance's PID.
- Stop the first instance with `SIGSTOP`. The second starts after ~5 seconds.

### Unit

- Missing or invalid pidfile.
- Pidfile points to another executable.
- Pidfile contains the current process PID.

### Integration

- Starting two instances leaves only the second running.
- An unresponsive first instance does not block startup.

## Status

Implemented
