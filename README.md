pyinstaller \
  --windowed --name SplitLedger \
  --add-data "people.json:." \
  --add-data "cards.json:." --add-data "config_path.txt:." split_ledger_gui.py
