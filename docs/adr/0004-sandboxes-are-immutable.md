# Sandboxes are immutable: recreated by hand, never migrated or removed by foundry

sbx fixes a sandbox's definition and mounts when it creates it, and hardening installs the managed settings once. So foundry writes a sandbox's definition once and never changes it. A sandbox that no longer matches what foundry would create (other session variables, older managed settings, another foundry's kit) is refused at launch, saying what differs and how to recreate it. foundry never removes a sandbox: removing one could lose work that wasn't pushed, so you do it yourself.

The cost: any change to the session variables or the managed settings means recreating every sandbox.

## Considered options

- **`foundry run --fresh`, removing and recreating the sandbox.** One flag could destroy unpushed work.
- **Migrating an outdated sandbox in place, or reusing it.** Its kit then failed inside the sandbox, or kept older hooks and permissions.
- **A `session.yaml` recording each launch.** foundry hands over to sbx and never learns how a run ended, so nothing could make the record true.

Source: #18, #13, #14.
