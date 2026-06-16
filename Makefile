SHELL := powershell.exe
.SHELLFLAGS := -NoProfile -Command

APP_NAME := SanBenedettoPOS
ICON_SOURCE := .\img\icona.png
ICON_FILE := .\img\icona.ico
APP_DIST_DIR := .\dist\$(APP_NAME)
APP_DIST_EXE := $(APP_DIST_DIR)\$(APP_NAME).exe

.PHONY: install run icon build portable installer clean

install:
	py -m pip install -r .\requirements.txt

run:
	py .\gui_app.py

icon:
	py .\build_icon.py $(ICON_SOURCE) $(ICON_FILE)

build: portable

portable: icon
	py -m PyInstaller --noconfirm --clean --onefile --windowed --name $(APP_NAME) --icon $(ICON_FILE) --add-data "menu_config.json;." --collect-data escpos .\gui_app.py
	if (Test-Path $(APP_DIST_DIR)) { Remove-Item $(APP_DIST_DIR) -Recurse -Force }
	New-Item -ItemType Directory -Path $(APP_DIST_DIR) | Out-Null
	Copy-Item .\dist\$(APP_NAME).exe $(APP_DIST_EXE)
	Copy-Item .\menu_config.json $(APP_DIST_DIR)\menu_config.json

installer: build
	if (Get-Command iscc -ErrorAction SilentlyContinue) { iscc .\installer.iss } elseif (Test-Path "$${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe") { & "$${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" .\installer.iss } else { throw "Inno Setup 6 non trovato. Installa Inno Setup oppure aggiungi iscc al PATH." }

clean:
	if (Test-Path .\build) { Remove-Item .\build -Recurse -Force }
	if (Test-Path .\dist) { Remove-Item .\dist -Recurse -Force }
	if (Test-Path .\$(APP_NAME).spec) { Remove-Item .\$(APP_NAME).spec -Force }