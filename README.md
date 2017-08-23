# PlexTrainingVideoScannerAndAgent
A Plex scanner and agent for training videos i.e. Pluralsight, Lynda.com, Udemy, etc.

![](images/main.png?raw=true)

This currently only works with Pluralsight, Udemy and Lynda.com offline files. The structure of the files is somewhat rigid, but it is pretty much how all of my files were organized.

Course Name/1. Chapter Name/Media File<br/>
i.e. Lynda.com.Angular2.for.NET.Developers\1. Course Overview\500547_01_02_XR15_SampleMovieDb.mp4

I have ignored the Exercise Files, Source Files, and Files directories so that they can be stored with the video files but not interfere with Plex scanning.

THIS IS A WORK IN PROGRESS!!<br/>
I obviously haven't accounted for every permutation of how you may have these files organized so as we all discover new patterns we can update the regex patterns to accomodate new permutations. Send a pull request if you add new regex patterns.

NO ARTWORK IS DOWNLOADED!!<br/>
So, this gets no information from any training site, there seemed to be no good way to locate show/course data, your best bet at this point is to manually go take a screen shot and add it as a poster in Plex.

The only automated thing the code does is use the Pluralsight, Udemy or Lynda.com in the folder name for the show to set the Network/Studio in Plex, this allows you to see all videos from each provider if you want.

AUTOMATIC SEASON NAMING!!<br/>
One really cool thing this does is use the section/chapter folder name as the season title. Previously it seemed there was no way to set the season title but I figured out a little hack to call into the Plex UI to set it. While it is cool, it makes the code super duper brittle, if Plex decides to change the UI it may break my code, but I'm willing to take that chance ;)

![](images/course.png?raw=true)

Also, finally, this is my first Python anything, I don't "know" the language, so if there are syntactical improvements please let me know. I felt like I was back doing VBScript (sorry python peeps!) trying to fumble through this.
