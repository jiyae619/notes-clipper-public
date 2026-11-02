// Notes-Clipper Runner — the program launchd starts for the watcher.
//
// macOS grants folder access (TCC: Downloads, Documents) per app, and judges a
// child process by the app that launched it. Running process_inbox.sh through
// this small signed bundle means you grant access to this one app, instead of
// giving /bin/bash Full Disk Access — which every bash script would inherit.
//
// Spawn, don't exec: exec would replace this binary with bash in the same
// process, and TCC would then see bash, not the app you granted.
#include <spawn.h>
#include <stdio.h>
#include <sys/wait.h>

extern char **environ;

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: %s <script> [args...]\n", argv[0]);
        return 64;
    }
    char *args[argc + 1];
    args[0] = "/bin/bash";
    for (int i = 1; i < argc; i++) args[i] = argv[i];
    args[argc] = NULL;

    pid_t pid;
    int err = posix_spawn(&pid, "/bin/bash", NULL, NULL, args, environ);
    if (err) {
        fprintf(stderr, "notes-clipper-runner: spawn failed (%d)\n", err);
        return 70;
    }
    int status;
    if (waitpid(pid, &status, 0) < 0) return 70;
    // Pass the script's exit code through, so `launchctl print` shows failures.
    return WIFEXITED(status) ? WEXITSTATUS(status) : 70;
}
