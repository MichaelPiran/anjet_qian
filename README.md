# Stampa scontrini personalizzati

Questo esempio usa il linguaggio ESC/POS, tipico delle stampanti termiche da 80 mm.

## Applicazione grafica con storage su file

Il progetto include anche una GUI locale per registrare vendite da banco.

- Il menu di bibite e cibo viene letto da `menu_config.json`.
- Ogni vendita viene salvata in `storico/sales_data.json`.
- Ogni movimento applicativo viene scritto in `logs/movements.log` con rotazione automatica.
- Per ogni vendita viene generato anche un file JSON in `storico/receipts/`, riusabile con `print_receipt.py`.
- Il contatore articoli venduti viene mantenuto in `storico/sales_data.json` e mostrato nella GUI.
- La GUI mostra anche uno storico filtrabile per data con incasso giornaliero.
- La stampa diretta parte dal pulsante di conferma se la sezione `printer` nel file di config e attivata.
- I prezzi sono mostrati come numeri semplici, senza simbolo euro, perche non si tratta di uno scontrino fiscale.
- All'avvio l'app crea automaticamente `storico/`, `storico/receipts/` e `logs/` accanto all'eseguibile; se trova un vecchio `sales_data.json` in root, lo migra al primo avvio.
- Se qualcosa va storto all'avvio, l'app mostra un messaggio leggibile e salva i dettagli in `logs/startup-error.log` invece di chiudersi senza indicazioni.

### Avvio GUI

```powershell
py .\gui_app.py
```

Se `py` non e disponibile nel tuo ambiente, usa il comando Python che hai installato, ad esempio:

```powershell
python .\gui_app.py
```

### Configurazione menu

Modifica `menu_config.json` per cambiare articoli, prezzi, formato dello scontrino e parametri stampante. Struttura di esempio:

```json
{
	"store_name": "Bar Centrale",
	"address": "Via Roma 12, 20100 Milano",
	"price_display": {
		"currency_symbol": "",
		"show_currency": false
	},
	"receipt": {
		"title": "Festa di Paese - Punto Ristoro",
		"show_time": true,
		"time_label": "Ora",
		"show_subtotal": false,
		"show_unit_price": false,
		"footer": "Grazie per aver festeggiato con noi",
		"effect_phrases": [
			"Che la festa continui!",
			"Un brindisi al paese!"
		]
	},
	"printer": {
		"enabled": true,
		"connection": "windows",
		"printer_name": "POS-80-Series-ok"
	},
	"menu": {
		"bibite": [
			{ "name": "Acqua Naturale", "price": 1.0, "color": "#0ea5e9" }
		],
		"cibo": [
			{ "name": "Toast", "price": 4.5, "color": "#facc15" }
		]
	}
}
```

Ogni elemento dentro `menu.bibite` e `menu.cibo` deve avere anche il campo `color`, espresso come colore esadecimale `#RRGGBB`, usato per il pulsante nella schermata principale.

La sezione `receipt` controlla il contenuto dello scontrino non fiscale:

- titolo
- visualizzazione dell'ora
- elenco frasi corte ad effetto, da cui l'app ne estrae una a ogni vendita
- etichette testuali come `Totale` o `Ora`

Per attivare la stampa diretta imposta `printer.enabled` a `true` e completa i parametri di collegamento della stampante.

Se la stampante e collegata via USB ma installata in Windows, la configurazione corretta resta quella per nome stampante:

```json
"printer": {
	"enabled": true,
	"connection": "windows",
	"printer_name": "POS-80-Series-ok",
	"no_cut": false
}
```

In questo scenario il cavo e USB, ma il backend usato dall'app e quello Windows spooler, esattamente come nel flusso gia usato con `print_receipt.py`.

### Makefile: run, build e installer

Il progetto include un `Makefile` con target pronti per ambiente Windows:

```powershell
make install
make run
make build
make portable
make installer
```

Target disponibili:

- `make install`: installa le dipendenze Python.
- `make run`: avvia la GUI.
- `make build`: genera il pacchetto portabile minimale in `dist/SanBenedettoPOS/`, con solo `SanBenedettoPOS.exe` e `menu_config.json`.
- `make portable`: genera l'eseguibile singolo e poi prepara la stessa cartella portabile in `dist/SanBenedettoPOS/`.
- `make installer`: genera un vero installer Windows con Inno Setup.
- `make clean`: rimuove cartelle di build.

Per `make installer` serve Inno Setup 6 installato. Il comando prova `iscc` dal `PATH` e, se non lo trova, usa il percorso standard di Inno Setup su Windows.

Se vuoi spostare l'app su un altro PC Windows senza installare Python, ti basta copiare l'intera cartella `dist/SanBenedettoPOS/`: contiene solo l'eseguibile standalone e il file di configurazione modificabile.

Per personalizzare l'icona di applicazione e installer, usa la cartella [img](img):

- [img/README.txt](img/README.txt)
- `img/icona.png`
- `img/icona.ico`

Il target `make icon` genera automaticamente `img/icona.ico` a partire da `img/icona.png`, e build/installer usano quella icona.

La GUI usa `tkinter`, che normalmente e gia inclusa in Python su Windows.

## 1. Installazione

Installa Python, poi i pacchetti necessari:

```powershell
pip install -r .\requirements.txt
```

Se vuoi usare il collegamento USB diretto su Windows, in alcuni casi serve anche un driver USB generico come WinUSB o libusb associato alla stampante tramite Zadig.

Se invece la stampante e gia installata in Windows e stampa dalla coda di stampa normale, spesso e meglio usare il backend Windows nativo invece di `usb`.

## 2. File JSON

Modifica `example_receipt.json` con i tuoi dati.

## 3. Esecuzione

### USB

```powershell
python .\print_receipt.py .\example_receipt.json --connection usb --vendor-id 0x0456 --product-id 0x0808
```

### Windows spooler

```powershell
py -m pip install pywin32
py .\print_receipt.py --list-printers
py .\print_receipt.py .\example_receipt.json --connection windows --printer-name "POS-80-Series-ok"
```

### Seriale

```powershell
python .\print_receipt.py .\example_receipt.json --connection serial --port COM3 --baudrate 9600
```

### Rete

```powershell
python .\print_receipt.py .\example_receipt.json --connection network --host 192.168.1.50
```

## Driver: cosa ti serve davvero?

Dipende da come colleghi la stampante.

- USB diretto: Windows puo vedere la stampante, ma per inviare comandi ESC/POS raw da Python puo servire WinUSB o libusb.
- Windows spooler: se la stampante e installata in Windows, spesso non serve toccare i driver USB; basta usare il nome stampante con `--connection windows`.
- Seriale/COM: di solito basta il driver USB-seriale del chipset, se la stampante espone una porta COM.
- Ethernet o Wi-Fi: in genere non serve un driver specifico per lo script, basta che la stampante sia raggiungibile via IP e supporti ESC/POS sulla porta 9100.

Se il modello Anjet80 Ultra Qian viene fornito con un driver Windows del produttore, installarlo e fare una stampa di prova da Windows e il modo piu rapido per verificare che la periferica funzioni. Per lo script, pero, la cosa decisiva e che il dispositivo accetti comandi ESC/POS sulla connessione scelta.

## Errore specifico: NotImplementedError su libusb

Se vedi un errore come questo:

```text
NotImplementedError: Operation not supported or unimplemented on this platform
```

significa quasi sempre che il backend `usb` sta provando ad aprire la stampante tramite libusb, ma Windows la sta gestendo con un driver di stampa classico oppure con un driver non compatibile con pyusb.

Le due strade corrette sono:

1. Se la stampante e gia installata in Windows, usa `--connection windows --printer-name "Nome stampante"`.
2. Se vuoi usare `--connection usb`, cambia il driver della periferica in WinUSB o libusb con Zadig.

In pratica, per il tuo errore, la prima prova da fare e questa:

```powershell
py -m pip install pywin32
py .\print_receipt.py --list-printers
py .\print_receipt.py .\example_receipt.json --connection windows --printer-name "POS-80-Series-ok"
```

Se hai gia eseguito `pip install pywin32` ma l'errore resta, il problema di solito e che `pip` ha installato il pacchetto in un Python diverso. In quel caso usa sempre:

```powershell
py -m pip install pywin32
```

e poi rilancia lo script con `py`.

Nel tuo caso il nome stampante registrato in Windows risulta `POS-80-Series-ok`, non `Anjet80 Ultra Qian`.

## Come trovare vendor ID e product ID

Su Windows:

1. Apri Gestione dispositivi.
2. Trova la stampante.
3. Apri Proprieta -> Dettagli.
4. Seleziona `ID hardware`.
5. Cerca valori come `VID_1234` e `PID_5678`.

Questi diventano `0x1234` e `0x5678` nello script.