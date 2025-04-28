# WSL Setup

## Contents

- [About](#about)
- [Prerequisites](#prerequisites)
- [Installing WSL2](#installing-wsl2)
- [Tips and Tricks](#tips-and-tricks)
- [Custom distributions](#Custom-distributions)
    - [Preparing a Stage3 tarball](#preparing-a-stage3-tarball)
    - [Importing the rootfs tar file](#importing-the-rootfs-tar-file)
- [Gentoo setup](#gentoo-setup)

## About

WSL setup guide for new installations.

## Prerequisites

- Basic familiarity with running PowerShell and Bash commands.
- [7zip file archiver](https://7-zip.org/download.html)
- (optional) Apply default configurations
    - `mkdir ~\.wsl`
    - `git clone https://github.com/elainajones/windows_home.git`
    - `Copy-Item -Recurse windows_home\.wsl* ~\`

## Installing WSL2

1. Start Menu > "Turn Windows features on or off" > Windows Subsystem for Linux  
   ![](img/enable-wsl.png)
    - You'll be prompted to restart to update. Complete before continuing.
2. `wsl --install`
3. `wsl -l -v`
    - Confirm the version is WSL2. If not, run  
      `wsl --set-default-version <Version#>`
    - If this fails to update and mentioned an unsupported kernel  
      package, download and install the [WSL2 Linux kernel update  
      package for x64 machines](https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi)

## Tips and Tricks

- Create a `~\.wsl` directory to organize WSL files.
- After installing a WSL distro, symlink `/boot/` to `~\.wsl\boot` so  
  custom kernel images can be easily configured in `~\.wslconfig` and  
  to reduce bloat inside the WSL installation.
- Common configuration files such as `/etc/apt/apt.conf` or  
  `/etc/portage/make.conf` can be symlinked to `~\.wsl\etc\` to make it  
  easier to manage common configurations across multiple installations.
    - This also makes it easy to backup these files from a single location.

## Custom distributions

Custom WSL installations can be made by simply importing a `.tar` file  
containing the root filesystem of your target distribution. Many custom  
distribution can be installed this way by using a virtual machine to  
create the `.tar` archive of a newly installed Linux distribution.  

Other distros such as Gentoo and Void Linux provide initial rootfs or  
stage files officially. In this example, Gentoo Linux will be used  
to demonstrate installing a custom distro

### Preparing a Stage3 tarball

1. Download the stage3 tarball.
    - [latest Current stage4 amd64 nomultilib openrc](https://distfiles.gentoo.org/releases/amd64/autobuilds/current-stage3-amd64-nomultilib-openrc/)
    - Stage3 is used to ensure compatibility by forcing the  
      installation to be 64-bit only.
2. Download the corresponding `.sha256` file.
    - This should be signed by the "Gentoo Linux Release Engineering  
      (Automated Weekly Release Key)" key from the [Signatures page](https://www.gentoo.org/downloads/signatures/).
    - If you're in a Linux environment now, fetch the key and verify  
      the `.sha256` file with `gpg --verify *.sha256`.
    - For new installs, verifying the hash is usually sufficient and the  
      signature can be verified after installing.
3. Get the SHA256 hash of the downloaded tarball and compare with the  
   hash inside the `.sha256` file to verify the file integrity. These  
   should match.
    - Windows: `Get-FileHash -A sha256 *tar.xz`.
    - Linux: `sha256sum *tar.xz`.
4. Uncompress the `tar.gz` image to `.tar`
    - Windows: Use [7zip file archiver](https://7-zip.org/download.html)
    - Linux: `gunzip *.tar.gz` or `gzip -d *tar.gz`

### Importing the rootfs tar file

1. Create a directory for the new vhdx file created during the import  
   step.
    - `mkdir ~\.wsl\gentoo`
2. Import the tar file.
    - `wsl --import gentoo ~\.wsl\gentoo <path\to\stage3.tar>`
3. Select the default WSL distro
    - `wsl -l -v` to list installed distros
    - `wsl -s <distro>` to set the default
4. Complete remaining installation steps for your distro
    - Gentoo: [Installing system tools](https://wiki.gentoo.org/wiki/Handbook:AMD64/Installation/Tools)
    - Gentoo: [Adding a user](https://wiki.gentoo.org/wiki/Handbook:AMD64/Installation/Finalizing#Adding_a_user_for_daily_use)
5. Set the default user in `/etc/wsl.conf`  
   ```
   [user]
   default = <user>
   ```

## Gentoo setup

1. Create symlinks
    - `ln -s /mnt/c/Users/<user>/.wsl/boot /boot`
    - `ln -s /mnt/c/Users/<user>/.wsl/etc/portage/make.conf /etc/portage/make.conf`
2. [Configuring Portage](https://wiki.gentoo.org/wiki/Handbook:AMD64/Installation/Base#Configuring_Portage)
    - Skip steps related to the `make.conf`
    - `emerge --sync`
    - `eselect profile list`
    - `ln -sf /usr/share/zoneinfo/US/Pacific /etc/localtime`
    - `emerge --ask vim`
    - `eselect editor list`
    - `vim /etc/locale.gen`
        - Add `en_US ISO-8859-1`
        - Add `en_US.UTF-8 UTF-8`
    - `locale-gen`
    - `eselect locale list`
    - `. /etc/profile`
3. [Finalizing](https://wiki.gentoo.org/wiki/Handbook:AMD64/Installation/Finalizing)
    - `emerge --ask sudo`
    - `useradd -m -G users,wheel -s /bin/bash gentoo`
    - `passwd gentoo`
    - `visudo`
        - Add `gentoo ALL=(ALL:ALL) NOPASSWD: ALL`
    - Set the default user in `/etc/wsl.conf`  
   ```
   [user]
   default = gentoo
   ```
    - `emerge --ask --verbose --update --deep --changed-use dev-vcs/git @world`
    - `exit` and `wsl` to login with `gentoo`
    - `mkdir ~/projects/ && cd ~/projects && git clone -j4 --recurse-submodules https://www.github.com/elainajones/linux_home.git`
        - This is a good place to make a backup export
    - `cp -ruTv linux_home/ ~/ && rm -rf ~/{.git,README.md}`
