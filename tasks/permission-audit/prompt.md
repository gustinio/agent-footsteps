The directory `site/` is a web root whose file permissions have drifted. The policy is:

1. Every directory has mode 755, except `secrets/`, which has mode 700.
2. Every regular file has mode 644, except that files ending in `.sh` have mode 755 and files directly inside `secrets/` have mode 600.

Change the modes so the whole tree follows the policy, without changing any file contents or names. Then write `fixed.txt` in the current directory, listing the path (relative to `site/`, for example `bin/deploy.sh`) of every file or directory whose mode you changed, one per line, sorted in byte order.
