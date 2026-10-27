# Each sandbox gets only its own role's credentials

Each sandbox gets a private ssh-agent holding only its role's key, and foundry checks from inside the sandbox that it sees exactly that key. A role's GitHub token is read by sbx from the host file, so foundry never handles it. Every launch, and `foundry prune`, kill the ssh-agents of sandboxes that are stopped or gone, so a key doesn't outlive its sandbox for long. An agent started in the last 10 minutes is spared, since it may belong to a launch in progress.

Source: #18, #3, #11.
