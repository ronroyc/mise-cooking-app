# Grocery list to Apple Reminders

A Mac Shortcut that copies what's left on the Slice'd grocery list into a "Groceries" list in Reminders. Reminders syncs to the iPhone through iCloud, so the list is on the phone at the store. Slice'd itself stays on the Mac: the Shortcut reads from `127.0.0.1`, and only Reminders (through your own iCloud) carries the list to the phone.

It works one way. Checking an item off in Reminders doesn't check it off in Slice'd.

## What Slice'd provides

`http://127.0.0.1:8000/api/grocery/text` returns the unchecked items as plain text, one per line:

```
Butter (2 tbsp)
Salmon fillet (2)
Garlic (3 cloves)
Lemon (1)
```

Slice'd has to be running for the Shortcut to work (the same server you open in Safari).

## One-time setup

1. Open **Reminders** and create a list called **Groceries** (File > New List).
2. Open **Shortcuts** and click **+** to make a new shortcut. Name it **Slice'd groceries to Reminders**.
3. In the search box on the right, find **Get Contents of URL** and drag it in. Set the URL to:
   `http://127.0.0.1:8000/api/grocery/text`
   Leave the method as GET.
4. Add **Split Text**. It should read "Split *Contents of URL* by *New Lines*".
5. Add **Repeat with Each**. It should read "Repeat with each item in *Split Text*".
6. Drag **Add New Reminder** inside the repeat block. Click the reminder text and pick **Repeat Item**. Set the list to **Groceries**.
7. Click the play button to run it. The first time, macOS asks for permission to use Reminders and to connect to 127.0.0.1. Allow both.

Optional: in the shortcut's details (the "i" button), turn on **Pin in Menu Bar** so it's one click away.

## Don't add the same item twice (optional)

Running the shortcut twice adds every item twice. To skip items that are already in Reminders:

1. Before **Repeat with Each**, add **Find Reminders**. Set it to find reminders where **List is Groceries** and **Is Not Completed**.
2. Inside the repeat block, wrap **Add New Reminder** in an **If**: "If *Reminders* does not contain *Repeat Item*".

This compares the text exactly. So if the amount on the Slice'd list changes (for example "Garlic (3 cloves)" becomes "Garlic (5 cloves)"), the new line is added next to the old one.

## Share button vs. this Shortcut

The **Share list** button on the Groceries page sends the whole list as one block of text. That's best for Notes or Messages. Sharing into Reminders that way makes a single reminder holding the whole list. For one reminder per item, use this Shortcut.
