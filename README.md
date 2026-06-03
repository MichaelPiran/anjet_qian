# Stampa scontrini personalizzati

Questo esempio usa il linguaggio ESC/POS, tipico delle stampanti termiche da 80 mm.

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