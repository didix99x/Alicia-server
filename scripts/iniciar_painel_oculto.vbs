Rem Abre o script sem janela (o painel e o Hermes rodam escondidos).
Set fso = CreateObject("Scripting.FileSystemObject")
pasta = fso.GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run """" & pasta & "\iniciar_painel.cmd" & """", 0, False
