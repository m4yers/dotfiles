#!/usr/bin/osascript

on run argv
  tell application "iTerm2"
    tell current session of current window
      set background image to argv's item 1
    end
  end
end
