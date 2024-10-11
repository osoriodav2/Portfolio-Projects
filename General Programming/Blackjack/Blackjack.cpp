#include <iostream>
#include <array>
#include <vector>
#include <string>
#include <algorithm>
#include <random>
#include <chrono>
#include <thread>

using namespace std;

class Card {
public:
    static const std::string FACES[14];

private:
    std::string suit;
    int face;

public:
    Card() : suit(""), face(0) {}
    Card(int face, std::string suit) : face(face), suit(suit) {}

    int getFace() const {
        if (face == 1) return 11;  // Adjust for ACE (1 -> 11)
        if (face >= 11) return 10;  // Adjust for JACK, QUEEN, KING
        return face;
    }

    std::string getSuit() const {
        return suit;
    }

    std::string toString() const {
        return FACES[face] + " of " + getSuit();
    }
};

// Static member initialization
const std::string Card::FACES[14] = {"ZERO", "ACE", "TWO", "THREE", "FOUR", "FIVE", "SIX", "SEVEN", "EIGHT", "NINE", "TEN", "JACK", "QUEEN", "KING"};

class Deck {
public:
    static const int NUMFACES = 13;
    static const int NUMSUITS = 4;
    static const int NUMCARDS = 52;
    static const std::string SUITS[NUMSUITS];

private:
    int topCardIndex;
    std::vector<Card> stackOfCards;

public:
    Deck() {
        for (int j = 0; j < NUMSUITS; ++j) {
            for (int i = 1; i <= NUMFACES; ++i) {
                stackOfCards.emplace_back(i, SUITS[j]);
            }
        }
        topCardIndex = NUMCARDS - 1;
    }

    void shuffle() {
        std::random_device rd;
        std::mt19937 g(rd());
        std::shuffle(stackOfCards.begin(), stackOfCards.end(), g);
        topCardIndex = NUMCARDS - 1;
    }

    Card nextCard() {
        if (topCardIndex >= 0) {
            return stackOfCards[topCardIndex--];
        } else {
            cerr << "No more cards in the deck!" << endl;
            return Card();
        }
    }
};

// Static member initialization
const std::string Deck::SUITS[NUMSUITS] = {"CLUBS", "SPADES", "DIAMONDS", "HEARTS"};

class Player {
private:
    std::vector<Card> hand;
    int winCount;

public:
    Player() : winCount(0) {}

    void addCardToHand(const Card& card) {
        hand.push_back(card);
    }

    void resetHand() {
        hand.clear();
    }

    int getHandValue() const {
        int sum = 0;
        for (const auto& card : hand) {
            sum += card.getFace();
        }
        return sum;
    }

    std::string toString() const {
        std::string result = "Hand: ";
        for (const auto& card : hand) {
            result += card.toString() + ", ";
        }
        return result;
    }

    int getHandSize() const {
        return hand.size();
    }
};

class Dealer : public Player {
private:
    Deck deck;

public:
    Dealer() : deck() {}

    void shuffleDeck() {
        deck.shuffle();
    }

    Card deal() {
        return deck.nextCard();
    }
};

class BlackJack {
private:
    Player player;
    Dealer dealer;

public:
    BlackJack() {}

    // Function to reset both player and dealer hands before a game
    void resetHands() {
        player.resetHand();
        dealer.resetHand();
    }

    void playGame() {
        resetHands();  // Ensure hands are reset before playing
        
        dealer.shuffleDeck();
        player.addCardToHand(dealer.deal());
        dealer.addCardToHand(dealer.deal());
        player.addCardToHand(dealer.deal());
        dealer.addCardToHand(dealer.deal());

        // Output section with visual enhancements
        printDivider();
        cout << "Welcome to BlackJack!" << endl;
        printDivider();
        cout << "\nDealing cards...\n\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));

        // Show Player and Dealer hands
        cout << "Your " << player.toString() << endl;
        cout << "Dealer's " << dealer.toString() << endl;

        int playerTotal = player.getHandValue();
        int dealerTotal = dealer.getHandValue();

        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        printDivider();
        cout << "Your total hand value is: " << playerTotal << endl;
        cout << "Dealer's hand value is: " << dealerTotal << endl;
        printDivider();

        // Player's decision to hit
        string choice;
        while (playerTotal < 21) {
            cout << "Would you like to hit? [Y/N]: ";
            cin >> choice;

            if (choice == "Y" || choice == "y") {
                player.addCardToHand(dealer.deal());
                playerTotal = player.getHandValue();
                cout << "\nYou hit! Your " << player.toString() << playerTotal << endl;
            }

            if (choice == "N" || choice == "n") {
                break;
            }
        }

        while (dealerTotal < 21 && dealerTotal < playerTotal && playerTotal < 21) {
                dealer.addCardToHand(dealer.deal());
                dealerTotal = dealer.getHandValue();
        }

        cout << "\nFinal Results:\n";
        std::this_thread::sleep_for(std::chrono::milliseconds(1000));
        printDivider();
        cout << "Your total: " << playerTotal << endl;
        cout << "Dealer's total: " << dealerTotal << endl;
        printDivider();

        if (playerTotal > 21) {
            cout << "\nYou busted! Dealer wins!\n";
        } else if (dealerTotal > 21 || playerTotal > dealerTotal) {
            cout << "\nYou win!\n";
        } else if (dealerTotal == playerTotal) {
            cout << "\nNobody won!\n";
        } else {
            cout << "\nDealer wins!\n";
        }
    }

    static void main() {
        BlackJack game;
        string playAgain;
        do {
            game.playGame();
            cout << "\nWould you like to play again? [Y/N]: ";
            cin >> playAgain;

        } while (playAgain == "Y" || playAgain == "y");

        cout << "\nThanks for playing!\n";
    }

private:
    void printDivider() const {
        cout << "\n========================================\n";
    }
};

int main() {
    BlackJack::main();
}
