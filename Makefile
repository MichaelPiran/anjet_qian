SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -Command

APP_NAME := AnjetQianPOS

.PHONY: install run build portable installer clean

install:
	py -m pip install -r .\requirements.txt

run:
	py .\gui_app.py

build:
	py -m PyInstaller --noconfirm --clean --windowed --name $(APP_NAME) --add-data "menu_config.json;." --add-data "example_receipt.json;." .\gui_app.py

portable:
	py -m PyInstaller --noconfirm --clean --onefile --windowed --name $(APP_NAME) --add-data "menu_config.json;." --add-data "example_receipt.json;." .\gui_app.py

installer: build
	if (Get-Command iscc -ErrorAction SilentlyContinue) { iscc .\installer.iss } elseif (Test-Path "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") { & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" .\installer.iss } else { throw "Inno Setup 6 non trovato. Installa Inno Setup oppure aggiungi iscc al PATH." }

clean:
	if (Test-Path .\build) { Remove-Item .\build -Recurse -Force }
	if (Test-Path .\dist) { Remove-Item .\dist -Recurse -Force }
	if (Test-Path .\$(APP_NAME).spec) { Remove-Item .\$(APP_NAME).spec -Force }