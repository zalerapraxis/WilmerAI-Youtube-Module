# WilmerAI-Youtube-Module
vibe-coded python module to pipe youtube transcripts into WilmerAI workflows


This module takes a youtube URL as input (usually from a chat), extracts the subtitles (skipping sponsor segments via SponsorBlock API, though I haven't tested if it actually works lmao) and spits the transcript out to be fed into a LLM. It's meant to be used as part of a [WilmerAI](https://github.com/SomeOddCodeGuy/WilmerAI) workflow.

There's also an `obsidian_save.py` script that takes markdown-formatted text & saves it as a `.md` file to be imported into Obsidian. Very much WIP. 

I don't know what I'm doing. Don't ask.


## Usage

### From Command Line

To use the module from the command line, execute the following command:

```bash
python youtube.py https://www.youtube.com/watch?v=7hBMbQ9de1g
```

### As a WilmerAI Module

To use this module within WilmerAI's PythonModule node, it should be called via a workflow. Below is an example of a workflow node configuration:

```json
{
    "title": "Python Module Caller",
    "module_path": "/home/eve/wilmerai/Configs/Scripts/youtube.py",
    "args": [
      "{chat_user_prompt_last_two}"
    ],
    "kwargs": {},
    "type": "PythonModule"
}
```