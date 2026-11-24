/* Bounded A51 boot diagnostics. Persistence uses the existing var_store claim
 * and archive; success is reported, never assumed. No direct reserved-RAM writes.
 */
#include "mini.h"

static void snapshot(int fd, const char *name)
{
    char buf[4608];
    size_t len = sizeof(buf);
    write(fd, name, strlen(name));
    write(fd, "\n", 1);
    if (sysctlbyname(name, buf, &len, NULL, 0) == 0 && len <= sizeof(buf)) {
        if (len && buf[len - 1] == 0) len--;
        write(fd, buf, len);
    } else {
        const char *failure = "diagnostic unavailable\n";
        write(fd, failure, strlen(failure));
    }
}

int main(int argc, char **argv, char **envp)
{
    (void)argc; (void)argv;
    const char *dir = "/private/var/mobile/Library/Logs";
    const char *path = "/private/var/mobile/Library/Logs/hakios-device-diagnostics.log";
    for (int attempt = 0; attempt < 3; attempt++) {
        usleep(20000000);
        mkdir(dir, 0755);
        int fd = open(path, O_WRONLY | O_CREAT | O_APPEND, 0644);
        if (fd < 0) continue;
        snapshot(fd, "kern.hakios_a51audio");
        snapshot(fd, "kern.hakios_a51touch");
        struct stat st;
        const char *app = stat("/private/preboot/apps/Iris.app/Iris", &st) == 0 ?
            "Iris executable present\n" : "Iris executable absent\n";
        write(fd, app, strlen(app));
        fsync(fd);
        close(fd);
        chown(path, 501, 501);
        pid_t pid = fork();
        if (pid == 0) {
            char *args[] = { "/redwood/bin/var_store", "save", NULL };
            execve(args[0], args, envp);
            _exit(127);
        }
        int status = -1;
        if (pid > 0 && wait4(pid, &status, 0, NULL) == pid)
            printf("A51 diagnostic archive save status=%d (zero means helper success)\n", status);
    }
    return 0;
}
