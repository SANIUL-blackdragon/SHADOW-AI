import requests

class ECHO:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_to_discord(self, message):
        """Sends a message to a Discord webhook."""
        data = {"content": message}
        try:
            response = requests.post(self.webhook_url, json=data)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"Error sending to Discord: {e}")

def main():
    """Main function to run the E.C.H.O. module."""
    # IMPORTANT: Replace with your Discord webhook URL
    webhook_url = "YOUR_WEBHOOK_URL"
    echo = ECHO(webhook_url)
    # Example usage:
    # echo.send_to_discord("SHADOW AI is online.")
    print("E.C.H.O. module is running.")

if __name__ == "__main__":
    main()
