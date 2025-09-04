# PowerShell tricks

## About

As much as we'd love to stay in the comfort of a unix-like environment, that's often not the case. Company-issued computers will likely be running the latest Windows version courtesy of your friends from your company's IT department. The reality is, Windows remains the operating system of choice for it's ease of use, compatibility, and most importantly enterprise support. And it's unsurpassed prevalence makes it clear it's here to stay.

Now from the perspective of Linux users and enthusiasts (of which I'm *certainly* no exception), this can seem rather daunting. But even relegated to the slow, bloated, and convoluted Windows ecosystem, we can employ some small tricks to improve the quality of our experiences.

## PowerShell profile

> A PowerShell profile is a script that runs when PowerShell starts. You can use the profile as a startup script to customize your environment. You can add commands, aliases, functions, variables, modules, PowerShell drives and more. You can also add other session-specific elements to your profile so they're available in every session without having to import or re-create them.
(see [About profiles](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_profiles)).

- Similar to `~/.bashrc` in Linux.
- Can be determined from the `$PROFILE` environment variable.
    - Current User, Current Host - $PROFILE
    - Current User, Current Host - $PROFILE.CurrentUserCurrentHost
    - Current User, All Hosts - $PROFILE.CurrentUserAllHosts
    - All Users, Current Host - $PROFILE.AllUsersCurrentHost
    - All Users, All Hosts - $PROFILE.AllUsersAllHosts


## Aliases

> An alias is an alternate name or nickname for a cmdlet or for a command element, such as a function, script, file, or executable file. You can use the alias instead of the command name in any PowerShell commands.
(See [About aliases](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_aliases))

```ps1
New-Alias -Name c -Value clear
```

