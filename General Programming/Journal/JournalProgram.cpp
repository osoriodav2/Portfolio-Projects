#include <iostream>     
#include <windows.h>
#include <fstream>
#include <string>
#include <vector>
#include <filesystem>

using namespace std;
namespace fs = std::filesystem;
class Journal {
private:
    string title;
    fstream afile;
public:
    Journal(string titleIn) : title(titleIn) {
        openFile();
    }

    ~Journal() {
        closeFile();
    }

    // Setter for the title member
    void setTitle(string titleIn) {
        title = titleIn; 
    }

    // Getter for the title member
    string getTitle() const {
        return title; 
    }

    // Method to open the journal file for reading and appending
    void openFile() {
        afile.open(title + ".txt", ios::app | ios::in | ios::out); // Open the file with append, read, and write modes
        if (!afile.is_open()) { // Check if the file failed to open
            cerr << "Failed to open file: " << title << ".txt" << endl; // Print error message
        }
    }

    void closeFile() {
        if (afile.is_open()) { // Check if the file is open
            afile.close(); // Close the file
        }
    }

    void writeEntry(const string& entry) {
        if (afile.is_open()) { // Check if the file is open
            afile << entry + "\n" << endl; // Write the entry to the file and adds three newlines
        } else {
            cerr << "File is not open for writing." << endl; // Print error message if file is not open
        }
    }

    // Method to load and display existing entries from the journal file
    void loadEntries() {
        if (afile.is_open()) {
            afile.clear(); 
            afile.seekg(0); 

            string line; // Variable to store each line read from the file
            if (!afile.good()) {
                cerr << "Error reading file." << endl;
                return;
            }
            
            while (getline(afile, line)) { // Read each line from the file
                cout << line << endl; // Print the line to the console
            }

            afile.clear(); // Clear EOF flag if it was set
            afile.seekp(0); // Move to the end of the file (ready for new writes)
        } else {
            cerr << "File is not open for reading." << endl; // Print error message if file is not open
        }
    }
};

void createNewEntry(); 
void viewEntries();  
void listJournalFiles(); 
void menu(); 
void clearConsole();

int main() {
    menu();
    return 0; 
}

void menu() {
    clearConsole();
    while (true) { 
        cout << "Journal Menu:\n";
        cout << "1. Create/Append Entry\n";
        cout << "2. View Existing Entries\n";
        cout << "3. List Journal Files\n";
        cout << "4. Exit\n"; 
        cout << "Enter your choice: ";

        int choice;
        cin >> choice;
        cin.ignore();

        switch (choice) { // Handle user's choice
            case 1:
                clearConsole();
                createNewEntry(); // Call function to create or append a journal entry
                break;
            case 2:
                clearConsole();
                viewEntries(); // Call function to view existing journal entries
                break;
            case 3:
                clearConsole();
                listJournalFiles(); // Call function to list all journal files
                break;
            case 4:
                clearConsole();
                return; // Exit the menu loop and end the program
            default:
                cout << "Invalid choice, please try again." << endl; // Handle invalid choice
                clearConsole();
                break;
        }
    }
}

// Function to create a new journal entry or append to an existing one
void createNewEntry() {
    listJournalFiles(); // List existing journal files
    cout << "Enter the title of the journal: "; 
    string title; // Variable to store the journal title
    getline(cin, title); // Read the title input

    Journal journal(title); // Create a Journal object with the provided title

    cout << "Existing entries in " << title << ": " << endl;
    journal.loadEntries(); // Display existing entries in the selected journal
    cout << endl;

    cout << "Write your entry: "; // Prompt user to write the journal entry
    string entry; // Variable to store the journal entry
    getline(cin, entry); // Read the journal entry

    journal.writeEntry(entry); // Write the entry to the file using the Journal object

    cout << "Entry created successfully!" << endl; // Print confirmation message
}

// Function to view existing entries from a specified journal
void viewEntries() {
    listJournalFiles(); // List all journal files
    cout << "Enter the title of the journal to view: "; // Prompt user for the title of the journal to view
    string title; // Variable to store the journal title
    getline(cin, title); // Read the title input

    if (!fs::exists(title + ".txt")) { // Check if the file exists
        cout << "Journal file does not exist." << endl; // Inform the user that the file does not exist
        cout << endl;
        return; // Exit the function if the file does not exist
    }

    Journal journal(title); // Create a Journal object for the specified title
    journal.loadEntries(); // Load and display entries from the journal file
    cout << endl;
}

// Function to list all journal files in the current directory
void listJournalFiles() {
    cout << "Listing all journal files:\n"; // Print header for the list of journal files
    for (const auto& entry : fs::directory_iterator(".")) { // Iterate over each entry in the current directory
        if (entry.is_regular_file() && entry.path().extension() == ".txt") { // Check if entry is a regular file with .txt extension
            cout << entry.path().stem().string() << endl; // Print the file name without extension
        }
    }
    cout << endl;
}

void clearConsole() {
    system("cls"); // Clear the console screen on Windows
}
