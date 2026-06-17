#include <iostream>  // Required for standard input/output streams
#include <winsock2.h>  // Winsock library for network programming
#pragma comment(lib, "ws2_32.lib")  // Link with Winsock 2.0 library

// Define constants
#define DEFAULT_PORT 54000  // The port number on which the server listens for connections
#define DEFAULT_BUFFER_SIZE 1024  // Buffer size for sending/receiving messages
// Function prototypes
bool initializeWinsock();
SOCKET createListeningSocket();
bool bindSocket(SOCKET listeningSocket);
bool listenForConnections(SOCKET listeningSocket);
SOCKET acceptClientConnection(SOCKET listeningSocket);
void handleClientCommunication(SOCKET clientSocket);
void cleanup(SOCKET listeningSocket, SOCKET clientSocket);

int main() {
    // Step 1: Initialize Winsock
    if (!initializeWinsock()) {
        return 1;
    }

    // Step 2: Create the server socket
    SOCKET listeningSocket = createListeningSocket();
    if (listeningSocket == INVALID_SOCKET) {
        return 1;
    }

    // Step 3: Bind the socket
    if (!bindSocket(listeningSocket)) {
        cleanup(listeningSocket, INVALID_SOCKET);
        return 1;
    }

    // Step 4: Listen for incoming connections
    if (!listenForConnections(listeningSocket)) {
        cleanup(listeningSocket, INVALID_SOCKET);
        return 1;
    }

    // Step 5: Accept a client connection
    SOCKET clientSocket = acceptClientConnection(listeningSocket);
    if (clientSocket == INVALID_SOCKET) {
        cleanup(listeningSocket, clientSocket);
        return 1;
    }

    // Step 6: Handle communication with the client
    handleClientCommunication(clientSocket);

    // Step 7: Cleanup resources
    cleanup(listeningSocket, clientSocket);
    return 0;
}

// Calls for version 2.2 of Winsock, and then sees if the return of the function intiates Winsock or not
bool initializeWinsock() {
    WSADATA wsData;
    int wsResult = WSAStartup(MAKEWORD(2, 2), &wsData);
    if (wsResult != 0) {
        std::cerr << "Failed to start Winsock. Error #" << wsResult << std::endl;
        return false;
    }
    std::cout << "Step 1" << std::endl;
    return true;
}

// Creates an IPv4 TCP connection (AF_INET, SOCK_STREAM), and checks if the socket is valid or not
SOCKET createListeningSocket() {
    SOCKET listeningSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (listeningSocket == INVALID_SOCKET) {
        std::cerr << "Socket creation failed. Error #" << WSAGetLastError() << std::endl;
    }
    std::cout << "Step 2" << std::endl;
    return listeningSocket;
}

// Function to bind the socket to an IP address and port
bool bindSocket(SOCKET listeningSocket) {
    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(DEFAULT_PORT);
    serverAddr.sin_addr.S_un.S_addr = INADDR_ANY;

    if (bind(listeningSocket, (sockaddr*)&serverAddr, sizeof(serverAddr)) == SOCKET_ERROR) {
        std::cerr << "Binding failed. Error #" << WSAGetLastError() << std::endl;
        return false;
    }
    std::cout << "Step 3" << std::endl;
    return true;
}

// Function to set the socket to listen for incoming connections
bool listenForConnections(SOCKET listeningSocket) {
    if (listen(listeningSocket, SOMAXCONN) == SOCKET_ERROR) {
        std::cerr << "Listen failed. Error #" << WSAGetLastError() << std::endl;
        return false;
    }
    std::cout << "Server is listening on port " << DEFAULT_PORT << "..." << std::endl;
    return true;
}

// Function to accept a client connection
SOCKET acceptClientConnection(SOCKET listeningSocket) {
    sockaddr_in clientAddr;
    int clientAddrSize = sizeof(clientAddr);
    SOCKET clientSocket = accept(listeningSocket, (sockaddr*)&clientAddr, &clientAddrSize);

    if (clientSocket == INVALID_SOCKET) {
        std::cerr << "Failed to accept connection. Error #" << WSAGetLastError() << std::endl;
    } else {
        std::cout << "Client connected!" << std::endl;
    }
    std::cout << "Step 5" << std::endl;
    return clientSocket;
}

// Function to handle communication with the client
void handleClientCommunication(SOCKET clientSocket) {
    char buffer[DEFAULT_BUFFER_SIZE];

    while (true) {
        ZeroMemory(buffer, DEFAULT_BUFFER_SIZE);

        // Receive a message from the client
        int bytesReceived = recv(clientSocket, buffer, DEFAULT_BUFFER_SIZE, 0);
        if (bytesReceived == SOCKET_ERROR) {
            std::cerr << "Error receiving message. Error #" << WSAGetLastError() << std::endl;
            break;
        }
        if (bytesReceived == 0) {
            std::cout << "Client disconnected." << std::endl;
            break;
        }

        // Print and echo the received message
        std::cout << "Received: " << buffer << std::endl;
        send(clientSocket, buffer, bytesReceived, 0);
    }
}

// Function to close sockets and clean up Winsock
void cleanup(SOCKET listeningSocket, SOCKET clientSocket) {
    if (clientSocket != INVALID_SOCKET) {
        closesocket(clientSocket);
    }
    if (listeningSocket != INVALID_SOCKET) {
        closesocket(listeningSocket);
    }
    WSACleanup();
}
