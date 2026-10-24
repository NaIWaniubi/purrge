# Purrge low-space alert for Windows (WPF). Keep this file ASCII-only: Windows PowerShell 5.1 reads
# script files in the system code page, so all user-facing text is passed in as arguments.
# Usage: powershell -STA -File alert.ps1 <title> <body> <usageLabel> <usedFraction 0-1> <iconPath> <primary> <secondary> [snapshot.png]
# Prints "scan" (primary button / Enter) or "later" (secondary / Esc / close).
param($Title, $Body, $Usage, $Used, $Icon, $Primary, $Secondary, $Snapshot)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName PresentationFramework, PresentationCore, WindowsBase

$dark = $false
try { $dark = (Get-ItemPropertyValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" AppsUseLightTheme) -eq 0 } catch {}
$c = if ($dark) {
  @{ card = "#2B2B2B"; edge = "#3D3D3D"; text = "#F3F3F3"; sub = "#B4B4B4"; track = "#454545"; btn2 = "#3A3A3A"; btn2edge = "#505050"; btn2text = "#F3F3F3" }
} else {
  @{ card = "#FFFFFF"; edge = "#E5E5E5"; text = "#1B1B1B"; sub = "#616161"; track = "#EBEBEB"; btn2 = "#FFFFFF"; btn2edge = "#D1D1D1"; btn2text = "#1B1B1B" }
}
$u = [math]::Max(0.0, [math]::Min(1.0, [double]$Used))
$fill = if ($u -ge 0.9) { "#E5484D" } elseif ($u -ge 0.75) { "#F2A33A" } else { "#2FBF71" }

[xml]$xaml = @"
<Window xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
        xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
        Title="Purrge" Width="480" SizeToContent="Height" WindowStyle="None" AllowsTransparency="True"
        Background="Transparent" ResizeMode="NoResize" Topmost="True" WindowStartupLocation="CenterScreen"
        FontFamily="Microsoft YaHei UI, Segoe UI" UseLayoutRounding="True">
  <Window.Resources>
    <Style x:Key="Btn" TargetType="Button">
      <Setter Property="Cursor" Value="Hand"/>
      <Setter Property="FontSize" Value="13"/>
      <Setter Property="MinWidth" Value="104"/>
      <Setter Property="Template">
        <Setter.Value>
          <ControlTemplate TargetType="Button">
            <Border x:Name="b" CornerRadius="6" Padding="18,7" Background="{TemplateBinding Background}"
                    BorderBrush="{TemplateBinding BorderBrush}" BorderThickness="{TemplateBinding BorderThickness}">
              <ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/>
            </Border>
            <ControlTemplate.Triggers>
              <Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Opacity" Value="0.86"/></Trigger>
              <Trigger Property="IsPressed" Value="True"><Setter TargetName="b" Property="Opacity" Value="0.72"/></Trigger>
            </ControlTemplate.Triggers>
          </ControlTemplate>
        </Setter.Value>
      </Setter>
    </Style>
  </Window.Resources>
  <Border x:Name="Card" Margin="18" CornerRadius="12" Background="$($c.card)" BorderBrush="$($c.edge)" BorderThickness="1">
    <Border.Effect><DropShadowEffect BlurRadius="28" ShadowDepth="6" Direction="270" Opacity="0.28"/></Border.Effect>
    <Grid Margin="24,20,24,22">
      <Grid.RowDefinitions><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/><RowDefinition Height="Auto"/></Grid.RowDefinitions>
      <DockPanel Grid.Row="0" Margin="0,0,0,14">
        <Button x:Name="Close" DockPanel.Dock="Right" Width="28" Height="28" Background="Transparent" BorderThickness="0"
                Cursor="Hand" FontFamily="Segoe MDL2 Assets" FontSize="10" Foreground="$($c.sub)" Content="&#xE8BB;">
          <Button.Template>
            <ControlTemplate TargetType="Button">
              <Border x:Name="b" CornerRadius="6" Background="Transparent"><ContentPresenter HorizontalAlignment="Center" VerticalAlignment="Center"/></Border>
              <ControlTemplate.Triggers><Trigger Property="IsMouseOver" Value="True"><Setter TargetName="b" Property="Background" Value="$($c.track)"/></Trigger></ControlTemplate.Triggers>
            </ControlTemplate>
          </Button.Template>
        </Button>
        <TextBlock Text="Purrge" FontSize="12" Foreground="$($c.sub)" VerticalAlignment="Center"/>
      </DockPanel>
      <Grid Grid.Row="1">
        <Grid.ColumnDefinitions><ColumnDefinition Width="Auto"/><ColumnDefinition Width="*"/></Grid.ColumnDefinitions>
        <Image x:Name="Icon" Width="64" Height="64" Margin="0,2,18,0" VerticalAlignment="Top" RenderOptions.BitmapScalingMode="HighQuality"/>
        <StackPanel Grid.Column="1">
          <TextBlock x:Name="TitleText" FontSize="17" FontWeight="SemiBold" Foreground="$($c.text)" TextWrapping="Wrap"/>
          <TextBlock x:Name="BodyText" FontSize="13" Foreground="$($c.sub)" TextWrapping="Wrap" LineHeight="21" Margin="0,6,0,0"/>
          <Grid x:Name="Track" Height="8" Margin="0,16,0,0">
            <Border CornerRadius="4" Background="$($c.track)"/>
            <Border x:Name="Fill" CornerRadius="4" Background="$fill" HorizontalAlignment="Left"/>
          </Grid>
          <TextBlock x:Name="UsageText" FontSize="12" Foreground="$($c.sub)" Margin="0,7,0,0"/>
        </StackPanel>
      </Grid>
      <StackPanel Grid.Row="2" Orientation="Horizontal" HorizontalAlignment="Right" Margin="0,22,0,0">
        <Button x:Name="Later" Style="{StaticResource Btn}" Background="$($c.btn2)" BorderBrush="$($c.btn2edge)" BorderThickness="1" Foreground="$($c.btn2text)" IsCancel="True"/>
        <Button x:Name="Scan" Style="{StaticResource Btn}" Background="#E9A51A" BorderBrush="#E9A51A" BorderThickness="1" Foreground="#1D1F22" FontWeight="SemiBold" Margin="10,0,0,0" IsDefault="True"/>
      </StackPanel>
    </Grid>
  </Border>
</Window>
"@

$win = [Windows.Markup.XamlReader]::Load((New-Object System.Xml.XmlNodeReader $xaml))
$f = @{}; foreach ($n in "Card", "Close", "Icon", "TitleText", "BodyText", "Track", "Fill", "UsageText", "Later", "Scan") { $f[$n] = $win.FindName($n) }
$f.TitleText.Text = $Title
$f.BodyText.Text = $Body
$f.UsageText.Text = $Usage
$f.Later.Content = $Secondary
$f.Scan.Content = $Primary
if ($Icon -and (Test-Path $Icon)) {
  $bmp = New-Object System.Windows.Media.Imaging.BitmapImage
  $bmp.BeginInit(); $bmp.UriSource = New-Object System.Uri((Resolve-Path $Icon).Path); $bmp.CacheOption = "OnLoad"; $bmp.EndInit()
  $f.Icon.Source = $bmp
}
$f.Track.Add_SizeChanged({ $f.Fill.Width = [math]::Max(8, $f.Track.ActualWidth * $u) })

if ($Snapshot) {
  # CI preview: lay out the card off-screen and save it as a PNG, no window or desktop needed
  $card = $f.Card
  $win.Content = $null
  $card.Measure((New-Object System.Windows.Size(480, [double]::PositiveInfinity)))
  $card.Arrange((New-Object System.Windows.Rect(0, 0, 480, $card.DesiredSize.Height)))
  $card.UpdateLayout()
  $f.Fill.Width = [math]::Max(8, $f.Track.ActualWidth * $u)
  $card.UpdateLayout()
  $rtb = New-Object System.Windows.Media.Imaging.RenderTargetBitmap(960, [int]($card.DesiredSize.Height * 2), 192, 192, [System.Windows.Media.PixelFormats]::Pbgra32)
  $rtb.Render($card)
  $enc = New-Object System.Windows.Media.Imaging.PngBitmapEncoder
  $enc.Frames.Add([System.Windows.Media.Imaging.BitmapFrame]::Create($rtb))
  $fs = [IO.File]::Create($Snapshot); $enc.Save($fs); $fs.Close()
  Write-Output "later"
  return
}

$script:result = "later"
$f.Scan.Add_Click({ $script:result = "scan"; $win.Close() })
$f.Later.Add_Click({ $win.Close() })
$f.Close.Add_Click({ $win.Close() })
$win.Add_MouseLeftButtonDown({ try { $win.DragMove() } catch {} })
$win.Add_ContentRendered({ $win.Activate() | Out-Null; $f.Scan.Focus() | Out-Null })
$win.ShowDialog() | Out-Null
Write-Output $script:result
