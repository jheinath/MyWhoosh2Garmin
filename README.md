<h1 align="center" id="title">myWhoosh2Garmin</h1>


<h2><b>Update 27/11/2024 - Garmin changed some things on their end. Looking into a solution but for now, it's back to manual uploading. 🙄</b></h2>
<p id="description">Python script to upload MyWhoosh .fit files to Garmin Connect for both MacOS and Windows.</p>

  
  
<h2>Features</h2>

*   Finds the .fit files from your MyWhoosh installation.
*   Fix the missing power & heart rate averages.
*   Removes the temperature.
*   Create a backup file to a folder you select.
*   Uploads the fixed .fit file to Garmin Connect.

<h2>🛠️ Installation Steps:</h2>

<p>1. Download myWhoosh2Garmin.py to your filesystem to a folder or your choosing.</p>
<p>2. Set up a venv
  TODO: add howto
</p>

<p>2. Go to the folder where you downloaded the script in a shell.</p>

MacOS: Terminal of your choice. 

Windows: Start > Run > cmd or Start > Run > powershell

<p>3. Run it to set things up.</p>

```
python3 myWhoosh2Garmin.py
or
python myWhoosh2Garmin.py
```

<p>3.1. First it will install Garth and Fit_tool package when you don't have it installed.

```
Installing collected packages: garth
Successfully installed garth-0.4.46
Installing collected packages: fit_tool
Successfully installed fit_tool-0.9.13
```
  
<p>4. Choose your backup folder.</p>

<h3>MacOS</h3>

![image](https://github.com/user-attachments/assets/2c6c1072-bacf-4f0c-8861-78f62bf51648)


<h3>Windows</h3>


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
2024-11-21 10:08:37,871 Successfully cleaned MyNewActivity-3.8.5.fit and saved it as MyNewActivity-3.8.5_2024-11-21_100837.fit.
2024-11-21 10:08:38,408 Duplicate activity found on Garmin Connect.
```

<p>(7. Or see below to automate the process)</p>

<h2>ℹ️ Automation tips</h2> 

What if you want to automate the whole process:
<h3>MacOS</h3>

PowerShell on MacOS (Verified & works)

You need Powershell

```shell
brew install powershell/tap/powershell
```

```powershell
# Define the JSON config file path
$configFile = "$PSScriptRoot\mywhoosh_config.json"
$myWhooshApp = "myWhoosh Indoor Cycling App.app"

# Check if the JSON file exists and read the stored path
if (Test-Path $configFile) {
    $config = Get-Content -Path $configFile | ConvertFrom-Json
    $mywhooshPath = $config.path
} else {
    $mywhooshPath = $null
}

# Validate the stored path
if (-not $mywhooshPath -or -not (Test-Path $mywhooshPath)) {
    Write-Host "Searching for $myWhooshApp"
    $mywhooshPath = Get-ChildItem -Path "/Applications" -Filter $myWhooshApp -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

    if (-not $mywhooshPath) {
        Write-Host " not found!"
        exit 1
    }

    $mywhooshPath = $mywhooshPath.FullName

    # Store the path in the JSON file
    $config = @{ path = $mywhooshPath }
    $config | ConvertTo-Json | Set-Content -Path $configFile
}

Write-Host "Found $myWhooshApp at $mywhooshPath"

Start-Process -FilePath $mywhooshPath

# Wait for the application to finish
Write-Host "Waiting for $myWhooshApp to finish..."
while ($process = ps -ax | grep -i $myWhooshApp | grep -v "grep") {
    Write-Output $process
    Start-Sleep -Seconds 5
}

# Run the Python script
Write-Host "$myWhooshApp has finished, running Python script..."
python3 "<PATH_WHERE_YOUR_SCRIPT_IS_LOCATED>/MyWhoosh2Garmin/myWhoosh2Garmin.py"
```

AppleScript (need to test further)

```applescript
TODO: needs more work
```

<h3>Windows</h3>

Windows .ps1 (PowerShell) file (Untested on Windows)
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
    $mywhooshPath = Get-ChildItem -Path "C:\PROGRAM FILES" -Filter "mywhoosh.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1

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
python "C:\Path\to\myWhoosh2Garmin.py"
```

<h2>💻 Built with</h2>

Technologies used in the project:

* Neovim
*   <a href="https://github.com/matin/garth">Garth</a>
*   tKinter
*   <a href="https://bitbucket.org/stagescycling/fit_tool/src/main/">Fit\_tool</a>
