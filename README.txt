FILE SHARE - QUICK START

1. Double-click Start File Share.bat.
2. Put files in the Shared Files folder, or upload them in the browser.
3. Select and copy the share link manually, then open it on your other device.
   Both devices must be on the same Wi-Fi / local network.
4. Download files, or upload files back from the other device.
5. Keep the launcher open. Press Ctrl+C in it to stop sharing.

If Windows Firewall asks, allow Python on your private network.
No extra Python packages are needed. Python 3.10 or newer is required.

Admin unlock enables creating folders and deleting files.
Your existing admin password is retained in fileshare.py (ADMIN_PASSWORD).
You can override it using the FILESHARE_ADMIN_PASSWORD environment variable.
Anyone with network access to the server can upload/download; admin unlock
only controls creating folders and deleting files. Use on a trusted network.

Uploads never replace existing files: duplicates become name (1).ext, etc.
Files are transferred in chunks so large files do not fill server memory.
The default shared folder is Shared Files beside this script.
Your other files in this tool's folder are not shared automatically.

To share another folder from Command Prompt:
  python fileshare.py 8000 "C:\path\to\your\folder"
The server tries port 80 first. If unavailable, it automatically chooses an
available port and displays the actual link.

To request another port:
  python fileshare.py 8001
To run without opening a browser:
  python fileshare.py --no-browser

Original script backup: fileshare.py.bak
