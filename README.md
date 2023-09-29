# Human Evaluation for Ghostbuster

This code generates a website and asks users to guess whether essays were written by humans or ChatGPT. To run it, simply navigate to the home directory of this repository and run:
```
flask run
```
If provided with a `config.json` file or the correct environment variables, the code will automatically log all guesses in a session (along with total accuracy) to an S3 bucket. A screenshot of the interface is shown below:

<img width="1440" alt="Screenshot 2023-09-29 at 1 53 23 PM" src="https://github.com/nickatomlin/ghostbuster-humaneval/assets/13228316/5cd18b1b-abf1-4198-852c-bc8a4d15458b">
