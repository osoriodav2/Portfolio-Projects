// Name: David Osorio
// Date: September 11th, 2024
// This program is intended to take two input files, a name.txt and a grades.txt, and create an output file containing data from both, organized.
    
#include <iostream>
#include <string>
#include <fstream>
#include <sstream>

std::ifstream inputNames("names.txt");
std::ifstream inputGrades("grades.txt");

class outputFile {
private:
    std::ifstream* nameFile;
    std::ifstream* gradeFile;
    int rows;
    int cols;
    int** gradeArray;
    float* avgArray; 
    std::string* nameArray;
    std::string* letterGrades;

    void allocateArrays() {
        gradeArray = new int*[rows];
        for (int i = 0; i < rows; ++i) {
            gradeArray[i] = new int[cols];
        }
        avgArray = new float[rows];
        nameArray = new std::string[rows]; 
        letterGrades = new std::string[rows];
    }

    void deallocateArrays() {
        for (int i = 0; i < rows; ++i) {
            delete[] gradeArray[i];
        }
        delete[] gradeArray;
        delete[] avgArray;
        delete[] nameArray;
        delete[] letterGrades;
    }

    void findRowAmount() {
        std::string line;
        rows = 0;
        while (std::getline(*gradeFile, line)) {
            ++rows;
        }
        gradeFile->clear();
        gradeFile->seekg(0);
    }

    void findColsAmount() {
        std::string line;
        if (std::getline(*gradeFile, line)) {
            std::stringstream ss(line);
            int number;
            cols = 0;
            while (ss >> number) {
                ++cols;
            }
        }
        gradeFile->clear();
        gradeFile->seekg(0);
    }
    
    void bubbleSort(int arr[], int n) {
        bool swapped;
        for (int i = 0; i < n - 1; ++i) {
            swapped = false;
            for (int j = 0; j < n - i - 1; ++j) {
                if (arr[j] > arr[j + 1]) {
                    std::swap(arr[j], arr[j + 1]);
                    swapped = true;
                }
            }
            if (!swapped) break; 
        }
    }

    bool hasNegativeGrades() {
        std::string line;
        gradeFile->clear();
        gradeFile->seekg(0);
        while (std::getline(*gradeFile, line)) {
            std::stringstream ss(line);
            int value;
            while (ss >> value) {
                if (value < 0) {
                    return true;
                }
            }
        }
        gradeFile->clear();
        gradeFile->seekg(0);
        return false;
    }
    
public:
    outputFile(): nameFile(&inputNames), gradeFile(&inputGrades)  {
        findRowAmount();
        findColsAmount();
        allocateArrays();
    }

    ~outputFile() {
        deallocateArrays();
    }

    void nameReader() {
        std::string line;
        int count = 0;
        while (std::getline(*nameFile, line) && count < rows) {
            nameArray[count] = line;  // Store name in predetermined array
            ++count;
        }
    }

    void gradeReader() {
        std::string line;
        int count = 0;
        while (std::getline(*gradeFile, line) && count < rows) {
            std::stringstream ss(line);
            int value;
            int colCount = 0;
            while (ss >> value) {
                if (colCount < cols) {
                    gradeArray[count][colCount] = value;
                    ++colCount;
                }
            }
            bubbleSort(gradeArray[count], cols); 
            ++count;
        }
        calculateAverages();
        calculateGradeLetter();
    }

    void calculateAverages() {
        for (int i = 0; i < rows; ++i) {
            float avgNumerator = 0;
            for (int j = 0; j < cols; ++j) {
                avgNumerator += gradeArray[i][j];
            }
            avgArray[i] = avgNumerator / cols;
        }
    }

    void calculateGradeLetter() {
        for (int i = 0; i < rows; ++i) {
            if (avgArray[i] >= 90) {
                letterGrades[i] = "A";
            } else if (avgArray[i] >= 80) {
                letterGrades[i] = "B";
            } else if (avgArray[i] >= 70) {
                letterGrades[i] = "C";
            } else if (avgArray[i] >= 60) {
                letterGrades[i] = "D";
            } else {
                letterGrades[i] = "F";
            }
        }
    }

    void createOutputFile() {
        if (hasNegativeGrades()) {
            std::cerr << "Output file could not be made. Check for any negative grades and try again." << std::endl;
            return;
        }
        nameReader();
        gradeReader();
        std::fstream outputFile;
        outputFile.open("output.txt", std::ios::app | std::ios::in | std::ios::out);
        for (int i = 0; i < rows; ++i) {
            outputFile << nameArray[i] << " ";
            for (int j = 0; j < cols; ++j) {
                outputFile << gradeArray[i][j] << " ";
            }
            outputFile << avgArray[i] << " " << letterGrades[i] << std::endl;
        }
        outputFile.close();
    }    
};


int main() {
    outputFile outputFile;
    outputFile.createOutputFile();

    return 0;
}
