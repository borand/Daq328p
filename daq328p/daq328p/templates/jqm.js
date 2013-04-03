$(document).ready(function() {
	console.log('Document ready');
	$('#json_res').attr('style', 'background-color:White; font-size:14px; height: 20em;');

	///////////////////////////////////////////////////////////////////////
	$('#json_cmd').keydown(function(e) {
		if (e.keyCode == 13) {
			var cmd = $("#json_cmd").val();			 			
			$(this).val("");
			// $("#json_res").text("");

			if (cmd == "clc") {
				console.log('Clear screen');
				$("#json_res").text("");
			} else {
				if (cmd == ''){
					console.log('Sending empty command');
					cmd = ' ';
				}
				else{
					console.log('Sending command: ' + cmd);
				}
					
				console.log('Sending command: ' + cmd);
				$("#json_res").append("cmd>" + cmd + "\n");

				$.getJSON('/query/' + cmd, "", function(data) {
					console.log(String(data));
					$("#json_res").html($("#json_res").text() + data + '\n');
					//$('#scratchpad').text(data);
					var psconsole = $('#json_res');
					psconsole.scrollTop(psconsole[0].scrollHeight - psconsole.height());
				});

			}
		}
	});
	///////////////////////////////////////////////////////////////////////
	$("#console_clear").click(function() {
		console.log('Pressed clear console button');
		$("#cmd_status").text("");
	});
	
	$("#options_threading").click(function() {
		console.log('Pressed options_threading button');
		SendCmd('options_threading',0)
		$("#cmd_status").text("Pressed options_ping button");
	});
	
	
	$("#options_ping").click(function() {
		console.log('Pressed options_ping button');
		SendCmd('ping',0)
		$("#cmd_status").text("Pressed options_ping button");
	});
	

	function SendCmd(cmd, val) {
		return $.getJSON('/cmd/', "cmd=" + cmd + "&val=" + val, function(data) {
			// //alert(data);
			$("#cmd_status").text(data);
		});
	}


}); 