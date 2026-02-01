Compilation Command:
```shell
pyinstaller \              
  --windowed  --name SplitLedger --icon wolf.icns \
  --add-data "people.json:." \
  --add-data "cards.json:." --add-data "config_path.txt:." split_ledger_gui.py
```

Modify default card and people information:<br>
~/Library/Application Support/SplitLedger/cards.json<br>
~/Library/Application Support/SplitLedger/people.json
