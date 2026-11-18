"""Small, testable view decisions for the cashier screen."""


def cashier_content_mode(search_text):
    """Show receipts until the cashier begins searching for an item."""
    return "items" if search_text.strip() else "receipts"
