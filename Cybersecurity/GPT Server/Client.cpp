#include <iostream>  // Required for standard input/output streams
#include <string>    // Required for string manipulations
#include <winsock2.h>  // Winsock library for network programming
#pragma comment(lib, "ws2_32.lib")  // Link with the Winsock 2.0 library

// Define constants
#define DEFAULT_PORT 54000  // Port number for connecting to the server
#define DEFAULT_BUFFER_SIZE 1024  // Buffer size for sending/receiving messages
//This is a test
// Function prototypes
bool initializeWinsock();
SOCKET createClientSocket();
bool connectToServer(SOCKET clientSocket, const std::string& serverIP);
void chatWithServer(SOCKET clientSocket);
void cleanup(SOCKET clientSocket);

int main() {
    // Step 1: Initialize Winsock
    if (!initializeWinsock()) {
        return 1;
    }

    // Step 2: Create the client socket
    SOCKET clientSocket = createClientSocket();
    if (clientSocket == INVALID_SOCKET) {
        return 1;
    }

    // Step 3: Connect to the server
    std::string serverIP = "127.0.0.1";  // Server IP (localhost)
    if (!connectToServer(clientSocket, serverIP)) {
        cleanup(clientSocket);
        return 1;
    }

    // Step 4: Chat with the server
    chatWithServer(clientSocket);

    // Step 5: Cleanup resources
    cleanup(clientSocket);
    return 0;
}

// Function to initialize Winsock
bool initializeWinsock() {
    WSADATA wsData;
    int wsResult = WSAStartup(MAKEWORD(2, 2), &wsData);
    if (wsResult != 0) {
        std::cerr << "Failed to start Winsock. Error #" << wsResult << std::endl;
        return false;
    }
    return true;
}

// Function to create the client socket
SOCKET createClientSocket() {
    SOCKET clientSocket = socket(AF_INET, SOCK_STREAM, 0);
    if (clientSocket == INVALID_SOCKET) {
        std::cerr << "Socket creation failed. Error #" << WSAGetLastError() << std::endl;
    }
    return clientSocket;
}

// Function to connect to the server
bool connectToServer(SOCKET clientSocket, const std::string& serverIP) {
    sockaddr_in serverAddr;
    serverAddr.sin_family = AF_INET;
    serverAddr.sin_port = htons(DEFAULT_PORT);
    serverAddr.sin_addr.S_un.S_addr = inet_addr(serverIP.c_str());

    int connResult = connect(clientSocket, (sockaddr*)&serverAddr, sizeof(serverAddr));
    if (connResult == SOCKET_ERROR) {
        std::cerr << "Connection failed. Error #" << WSAGetLastError() << std::endl;
        return false;
    }

    std::cout << "Connected to the server!" << std::endl;
    return true;
}

// Function to handle chat communication with the server
void chatWithServer(SOCKET clientSocket) {
    char buffer[DEFAULT_BUFFER_SIZE];
    std::string userInput;

    while (true) {
        // Prompt the user to enter a message
        std::cout << "Enter message: ";
        std::getline(std::cin, userInput);

        // Check if the user wants to exit
        if (userInput == "exit") {
            std::cout << "Disconnecting..." << std::endl;
            break;
        }

        // Send the user's message to the server
        int sendResult = send(clientSocket, userInput.c_str(), userInput.size() + 1, 0);
        if (sendResult == SOCKET_ERROR) {
            std::cerr << "Send failed. Error #" << WSAGetLastError() << std::endl;
            break;
        }

        // Receive the server's response
        ZeroMemory(buffer, DEFAULT_BUFFER_SIZE);
        int bytesReceived = recv(clientSocket, buffer, DEFAULT_BUFFER_SIZE, 0);
        if (bytesReceived > 0) {
            std::cout << "Server: " << std::string(buffer, 0, bytesReceived) << std::endl;
        }
    }
}

// Function to close the socket and clean up Winsock
void cleanup(SOCKET clientSocket) {
    closesocket(clientSocket);
    WSACleanup();
}
