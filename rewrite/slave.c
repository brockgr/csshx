#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <signal.h>
#include <strings.h>
#include <sys/errno.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <sys/un.h>

pid_t child_pid;

void done () {
    fprintf(stderr, "Close connection\n");
    kill(child_pid, SIGTERM);
    exit(0);
}

int setup_socket (char *path) {
    struct  sockaddr_un addr;

    int sock = socket(AF_UNIX, SOCK_STREAM, 0);
    if (sock < 0) {
        perror("socker() failed");
        done();
    }

    bzero(&addr, sizeof(addr));
    addr.sun_family = AF_UNIX;
    strcpy(addr.sun_path, path);

    if (connect(sock, (struct sockaddr *) &addr, sizeof(addr)) < 0) {
        perror("connect() failed");
        done();
    }

    return sock;
}


void send_greeting(int sock, char *id, char* host) {
    char buffer[1024];
    snprintf(buffer, 1024, "slave %s %s\n\0", id, host);
    send(sock, buffer, strlen(buffer), 0);
    fprintf(stderr, buffer);
}


int main (int ARGC, char *ARGV[]) {

    chdir("/");

    if (ARGC < 4) {
        fprintf(stderr, "Usage: %s path slave_id ssh_host ssh_args\n", ARGV[0]);
        exit(1);
    }

    while (1) {
        child_pid = fork();

        if (child_pid < 0) {
            if (errno == EAGAIN) {
                sleep(10);
            } else {
                perror("fork() failed");
                exit(1);
            }
        } else if (child_pid == 0) {
            char *new_argv[256];
            new_argv[0] = "ssh";
    
            int i;
            for (i=3; (i<ARGC) && (i<256-1); i++) new_argv[i-2] = ARGV[i];
            new_argv[i] = 0;
    
            execv("/usr/bin/ssh", new_argv);
            perror("excecv() failed");
            exit(255);
        } else {
            close(fileno(stdout));
    
            signal(SIGTTOU, SIG_IGN);
            signal(SIGCHLD, done);
    
            FILE *fp;
            int sock = setup_socket(ARGV[1]);
            fp = fdopen(sock, "r");
    
            send_greeting(sock, ARGV[2], ARGV[3]);
    
            int c;
            while ((c = fgetc(fp)) > 0) {
                if (ioctl(fileno(stdin), TIOCSTI, (char*) &c) < 0) {
                    perror("ioctl(stdin, TIOCSTI) failed");
                }
            }
            fprintf(stderr, "Slave closed\n");
            done();
        }
    }
}
