<h1>Apple Script to automate Garmin Upload</h1>
<p>The app will run and constantly check (every 30 seconds) whether MyWhoosh is running. Once started, it will listen to My Whoosh being quit/exited. In case My Whoosh was exited/quit, it will run the myWhoosh2Garmin.py script that needs to be installed and setup previously.</p>
<h2>🛠️ Installation Steps:</h2>
<ol>
  <li>Download MyWhoosh2Garmin-AS.scpt to your filesystem to a folder of your choosing.</li>
  <li>Go to the folder where you downloaded the script via Mac Finder.</li>
  <li>Open the script in the Apple Script Editor and set the property <code>pythonScriptPath</code> to the location where you downloaded the 
  <code>myWhoosh2Garmin.py</code> script.</li>
  
```
property targetApp : "MyWhoosh Indoor Cycling App"
property pythonScriptPath : "/path/to/myWhoosh2Garmin.py"
property appRunning : false

on idle
	if application targetApp is running then
		set appRunning to true
	else if appRunning then
		set appRunning to false
		performActionOnExit()
	end if
	return 30 -- Check every 30 seconds
end idle

on performActionOnExit()
	do shell script "python3 " & quoted form of pythonScriptPath
end performActionOnExit

on quit
	continue quit
end quit

```

  <li>After changing the property file, export the file as an app. (TODO: screenshot of export)</li>
  <li>Please select xyz as an export option.</li>
  <li>Store the app at a location of your choice.</li>
  <li>Before running the script, you need to grant the app full access to your hard drive. Otherwise, you will be prompted each time to allow access when the myWhoosh2Garmin is executed. Please search the web for a guide, given it slightly depends on your Mac OS version.</li>
  <li>Now you can run t</li>
</ol>
