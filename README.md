<h1 align="center" id="title">myWhoosh2Garmin</h1>

<p id="description">Python script to upload MyWhoosh .fit files to Garmin Connect for both MacOS and Windows.</p>

  
  
<h2>🧐 Features</h2>

*   Finds the .fit files from your MyWhoosh installation.
*   Fix the missing power & heart rate averages.
*   Removes the temperature.
*   Create a backup file to a folder you select.
*   Uploads the fixed .fit file to Garmin Connect.

<h2>🛠️ Installation Steps:</h2>

<p>1. Download myWhoosh2Garmin.py to your filesystem to a folder or your choosing.</p>

<p>2. Go to the folder where you downloaded the script in a terminal.</p>

<p>3. Run it to set things up.</p>

```
python3 myWhoosh2Garmin.py
```

<p>3.1. First it will install Garth and Fit_tool package when you don't have it installed.

```
Installing collected packages: garth
Successfully installed garth-0.4.46
Installing collected packages: fit_tool
Successfully installed fit_tool-0.9.13
```
  
<p>4. Choose your backup folder.</p>

![image](https://github.com/user-attachments/assets/d1540291-4e6d-488e-9dcf-8d7b68651103)

<p>5. Enter your Garmin Connect credentials</p>

```
2024-11-21 10:08:04,014 No existing session. Please log in.
Username: <YOUR_EMAIL>
Password:
2024-11-21 10:08:33,545 Authenticating...

2024-11-21 10:08:37,107 Successfully authenticated!
```

<p>6. Run the script when you're done riding or running.</p>

```
2024-11-21 10:08:37,107 Checking for .fit files in directory: <YOUR_MYWHOOSH_DIR_WITH_FITFILES>.
2024-11-21 10:08:37,107 Found the most recent .fit file: MyNewActivity-3.8.5.fit.
2024-11-21 10:08:37,107 Cleaning up <YOUR_BACKUP_FOLDER>yNewActivity-3.8.5_2024-11-21_100837.fit.
2024-11-21 10:08:37,855 Cleaned-up file saved as <YOUR_BACKUP_FOLDER>MyNewActivity-3.8.5_2024-11-21_100837.fit
2024-11-21 10:08:37,871 Successfully cleaned MyNewActivity-3.8.5.fitand saved it as MyNewActivity-3.8.5_2024-11-21_100837.fit.
2024-11-21 10:08:38,408 Duplicate activity found on Garmin Connect.
```

<p>(7. Or see below to automate the process)</p>

<h2>ℹ️ Automation tips</h2> 

What if you want to automate the whole process:
<h3>MacOS</h3>
AppleScript

```applescript
-- Define the text file path to store mywhoosh.app's location
set textFilePath to (POSIX path of (path to me)) & "mywhoosh_path.txt"

-- Read the stored path from the text file
set mywhooshPath to ""
try
    set mywhooshPath to do shell script "cat " & quoted form of textFilePath
on error
    set mywhooshPath to ""
end try

-- Check if the stored path is valid
if mywhooshPath is not "" then
    try
        do shell script "test -d " & quoted form of mywhooshPath
    on error
        set mywhooshPath to ""
    end try
end if

-- Search for mywhoosh.app if no valid path is found
if mywhooshPath is "" then
    set mywhooshPath to do shell script "mdfind 'kMDItemFSName == \"mywhoosh.app\"' | head -n 1"
    if mywhooshPath is "" then
        return -- Exit if mywhoosh.app is not found
    end if
    -- Store the path in the text file
    do shell script "echo " & quoted form of mywhooshPath & " > " & quoted form of textFilePath
end if

-- Run mywhoosh.app
tell application "Finder"
    open application file mywhooshPath
end tell

-- Wait for mywhoosh to finish
repeat
    set appRunning to (do shell script "ps aux | grep -v grep | grep -c " & quoted form of "mywhoosh.app") as integer
    if appRunning = 0 then exit repeat
    delay 5
end repeat

-- Run the Python script
do shell script "python3 /path/to/mywhoosh.py"
```
Bash

```bash
#!/bin/bash

# Define the path to store the `mywhoosh` executable location
config_file="$(dirname "$0")/mywhoosh_path.txt"

# Read the stored path from the text file, if it exists
if [[ -f "$config_file" ]]; then
    mywhoosh_path=$(<"$config_file")
else
    mywhoosh_path=""
fi

# Check if the stored path is valid
if [[ -n "$mywhoosh_path" && -e "$mywhoosh_path" ]]; then
    echo "Using stored path: $mywhoosh_path"
else
    # Search for mywhoosh.exe if no valid path is found
    echo "Searching for mywhoosh.exe..."
    mywhoosh_path=$(find / -name "mywhoosh.exe" 2>/dev/null | head -n 1)
    
    if [[ -z "$mywhoosh_path" ]]; then
        echo "mywhoosh.exe not found!"
        exit 1
    fi
    
    # Store the found path in the text file
    echo "$mywhoosh_path" > "$config_file"
    echo "Found and saved path: $mywhoosh_path"
fi

# Start mywhoosh.exe
echo "Starting mywhoosh.exe..."
"$mywhoosh_path" &

# Wait for the process to finish
echo "Waiting for mywhoosh.exe to finish..."
while pgrep -f "$(basename "$mywhoosh_path")" >/dev/null; do
    sleep 5
done

# Run the Python script
echo "mywhoosh.exe finished. Running Python script..."
python3 /path/to/mywhoosh.py

```
<h3>Windows</h3>

Windows .ps1 (PowerShell) file
```powershell
# Define the JSON config file path
$configFile = "$PSScriptRoot\mywhoosh_config.json"

# Check if the JSON file exists and read the stored path
if (Test-Path $configFile) {
    $config = Get-Content -Path $configFile | ConvertFrom-Json
    $mywhooshPath = $config.path
} else {
    $mywhooshPath = $null
}

# Validate the stored path
if (-not $mywhooshPath -or -not (Test-Path $mywhooshPath)) {
    Write-Host "Searching for mywhoosh.exe..."
    $mywhooshPath = Get-ChildItem -Path "C:\" -Filter "mywhoosh.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

    if (-not $mywhooshPath) {
        Write-Host "mywhoosh.exe not found!"
        exit 1
    }

    $mywhooshPath = $mywhooshPath.FullName

    # Store the path in the JSON file
    $config = @{ path = $mywhooshPath }
    $config | ConvertTo-Json | Set-Content -Path $configFile
}

Write-Host "Found mywhoosh.exe at $mywhooshPath"

# Start mywhoosh.exe
Start-Process -FilePath $mywhooshPath

# Wait for the application to finish
Write-Host "Waiting for mywhoosh to finish..."
while (Get-Process -Name "mywhoosh" -ErrorAction SilentlyContinue) {
    Start-Sleep -Seconds 5
}

# Run the Python script
Write-Host "mywhoosh has finished, running Python script..."
python "C:\Path\to\mywhoosh.py"
```

<h2>💻 Built with</h2>

Technologies used in the project:

* Neovim
*   Garth
*   tKinter
*   Fit\_tool
