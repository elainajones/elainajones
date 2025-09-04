# Net Use

## Mounting a network drive

Example command:
```ps1
net use <drive>: \\<hostname>\<root> /user:<username> [password]
```

## Unmounting a network drive

To unmount a specific drive letter.
```ps1
net use <drive>: /delete
```

To unmount all connections.
```ps1
net use * /delete
```
