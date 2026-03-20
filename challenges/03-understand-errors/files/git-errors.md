# Common Git Errors — Decode them with gh copilot explain!

## Error 1: Push Rejected
```
error: failed to push some refs to 'git@github.com:user/repo.git'
hint: Updates were rejected because the remote contains work that you do not have locally.
hint: Integrate the remote changes (e.g. 'git pull ...') before pushing again.
```

## Error 2: Merge Conflict
```
CONFLICT (content): Merge conflict in src/app.py
Automatic merge failed; fix conflicts and then commit the result.
```

## Error 3: Detached HEAD
```
HEAD detached at a1b2c3d
nothing to commit, working tree clean
```

## Error 4: Untracked Files Will Be Overwritten
```
error: Your local changes to the following files would be overwritten by merge:
    config/settings.py
Please commit your changes or stash them before you merge.
```

## Error 5: Authentication Failed
```
remote: Invalid username or password.
fatal: Authentication failed for 'https://github.com/user/repo.git/'
```

## Error 6: Repository Not Found
```
ERROR: Repository not found.
fatal: Could not read from remote repository.
Please make sure you have the correct access rights and the repository exists.
```

## Error 7: Rebase Conflict
```
CONFLICT (content): Merge conflict in README.md
error: could not apply 3a4b5c6... Add new feature
hint: Resolve all conflicts manually, mark them as resolved with
hint: "git add/rm <conflicted_files>", then run "git rebase --continue".
```
