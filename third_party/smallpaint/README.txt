smallpaint by karoly zsolnai - zsolnai@cg.tuwien.ac.at

render, modify, create new scenes, tinker around, and most of all:
have fun!

This program is used as an educational learning tool on the Rendering
course at TU Wien. Course webpage:
http://cg.tuwien.ac.at/courses/Rendering/

This UI serves as an educational learning tool to see the progressions
and experience the different renderes with different input.
created by Michael Oppitz  - e1227129@student.tuwien.ac.at	

Executables for Windows and Linux are provided in the folders "binary_win32"
and "binary_linux". If changes were made to the source code, rebuilding the 
solutions is necessary:
				
Building (Windows):
	- If you didn't already: Download and install Qt (tested with Version 5.10):
				- Qt: https://www.qt.io/download
	- Delete everything from the "binary_win32" folder.
	- Open the "Smallpaint.pro" file with the Qt Creator.
	- Go to the Build Settings and edit the build configuration (i.e., set to Release)
	- Change the build directory to the path of "binary_win32".
	- Build the project.
	- Remove everything, but the "Smallpaint.exe".
	- Open a console and call the command: 
				%PATH_TO_QT_KIT%\windeployqt.exe . 				(the dot is important)
	- If you are missing some dependencies look for them in the dependecy folder or online.

Building (Linux):
	- If you didn't already: Download and install Qt (tested with Version 5.10):
				- Qt: https://www.qt.io/download
	- Remove everything in the "binary_linux" folder and open a terminal there.
	- Call the commands:
				%PATHTOQT%/Qt5.7.0/5.7/gcc_64/bin/qmake ../src_gui
				make -j4
	- If you're missing some dependencies, run "ldd %PROGRAM%" and see what it links to.