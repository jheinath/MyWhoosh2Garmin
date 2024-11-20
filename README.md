<h1 align="center" id="title">myWhoosh2Garmin</h1>

<p id="description">Python script to upload MyWhoosh .fit files to Garmin Connect for both MacOS and Windows.</p>

  
  
<h2>🧐 Features</h2>

*   Finds the .fit files from your MyWhoosh installation.
*   Fix the missing power & heart rate averages.
*   Removes the temperature.
*   Create a backup file to a folder you select.
*   Uploads the fixed .fit file to Garmin Connect.

<h2>🛠️ Installation Steps:</h2>

<p>1. Download myWhoosh2Garmin.py to your filesystem</p>

<p>2. Go to the folder where you downloaded the script in a terminal</p>

<p>3. Run it to set things up</p>

```
python3 myWhoosh2Garmin.py
```

<p>4. Choose your backup folder</p>

<p>5. Enter your Garmin Connect credentials</p>

<p>6. Run the script when you're done riding or running</p>

<h2>ℹ️ Automation tips</h2> 

What if you want to automate the whole process:
<h3>MacOS</h3>
AppleScript

```applescript
-- Start mywhoosh.app
tell application "mywhoosh"
    activate
end tell

-- Wait until the application quits
repeat while application "mywhoosh" is running
    delay 1
end repeat

-- Run the Python script
do shell script "python3 ~/path/to/mywhoosh.py"

```
Bash

```bash
#!/bin/bash

# Path to the mywhoosh.app application
APP_PATH="/Applications/mywhoosh.app"

# Start the mywhoosh.app and wait for it to finish
echo "Starting mywhoosh.app..."
open -W "$APP_PATH"

# Check if the application exited successfully
if [ $? -eq 0 ]; then
    echo "mywhoosh.app has finished. Now running Python script..."
    # Run the Python script
    python3 mywhoosh.py
else
    echo "mywhoosh.app encountered an error."
    exit 1
fi
```
<h3>Windows</h3>

Windows .bat file
```bash
@echo off

:: Start mywhoosh.exe (adjust with correct path)
start "" "C:\Path\to\mywhoosh.exe"

:: Wait for the application to finish
echo Waiting for mywhoosh to finish...
:loop
tasklist /fi "imagename eq mywhoosh.exe" 2>NUL | find /I "mywhoosh.exe" >NUL
if not errorlevel 1 (
    timeout /t 5 /nobreak > NUL
    goto loop
)

:: Once the app finishes, run the Python script
echo mywhoosh has finished, running Python script...
python C:\Path\to\mywhoosh.py
```
Windows .ps1 (PowerShell) file
```bash
# Start mywhoosh.exe (adjust with correct path)
Start-Process "C:\Path\to\mywhoosh.exe"

# Wait for the application to finish
Write-Host "Waiting for mywhoosh to finish..."
while (Get-Process "mywhoosh" -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 5
}

# Once the app finishes, run the Python script
Write-Host "mywhoosh has finished, running Python script..."
python C:\Path\to\mywhoosh.py
```

<h2>💻 Built with</h2>

Technologies used in the project:

*   Garth
*   tKinter
*   Fit\_tool
