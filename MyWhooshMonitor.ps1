# Start mywhoosh.exe
Start-Process .\Start.lnk

# Wait for the application to finish
Write-Host "Waiting for $myWhooshApp to finish..."
while (Get-Process -Name MyWhoosh) {
    Write-Output $process
    Start-Sleep -Seconds 5
    Write-Output Sleep 5
}

# Run the Python script
Write-Host "$myWhooshApp has finished, running Python script..."
python ./myWhoosh2Garmin.py
