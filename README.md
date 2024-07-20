# Huh?
This is an attempt to map [DeLanda's usage](https://web.archive.org/web/20240203233005/https://www.cddc.vt.edu/host/delanda/pages/algorithm.htm) of the [genetic algorithm](https://www.youtube.com/watch?v=50-d_J0hKz0) as a generative process to for synthesizer parameters. The goal is to create patches that are interesting, generative, and surprising, rather than sticking to a few default behaviors of patch-making.

It works by:

 - iterating through randomized values for the synth
 - applying quanitative "fit" measures of "intensity" to them
 - honing them over generations. 

   The "intensive property" here is (unfortunately) the users' own subjective sense of the sound quality. To facilitate this, I'm creating a 1 to 8 "voting system" based on the [LPD-8](https://www.akaipro.com/lpd8), which I have lying around. Totally unnecessary, but feels nicer than a keyboard.
