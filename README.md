# chesslens

Port mapping for reaching Docker container hosted on WSL -

```
Powershell

> netsh interface portproxy add v4tov4 listenport=<PORT> listenaddress=0.0.0.0 connectport=<PORT> connectaddress=<eth0 IP of WSL>
> netsh advfirewall firewall add rule name="Flask PORT" dir=in action=allow protocol=TCP localport=<PORT>
```

Live Container logs -
```
$ sudo docker logs -f <CONTAINER-ID>
```
