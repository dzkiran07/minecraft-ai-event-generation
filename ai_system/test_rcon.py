from mcrcon import MCRcon

with MCRcon("localhost", "test123", port=25575) as mcr:
       response = mcr.command("weather thunder")
       print(response)