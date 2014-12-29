#!/usr/bin/env python3

## A Python Tutorial System
## Copyright (C) 2009,2010  Peter Robinson <pjr@itee.uq.edu.au>
##
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License
## as published by the Free Software Foundation; either version 2
## of the License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, write to the Free Software
## Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
## 02110-1301, USA.

"""The MyPyTutor application."""

import tkinter as tk
import os

from tutorlib.gui.app import TutorialApp


def main():
    """The main entry point for MyPyTutor."""

    root = tk.Tk()
    TutorialApp(root)
    root.mainloop()
    
if __name__ == '__main__': 
    main()
