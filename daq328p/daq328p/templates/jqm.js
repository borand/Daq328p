$(document).ready(function() {
	console.log('Document ready');
	$('#json_res').attr('style', 'background-color:White; font-size:14px; height: 15em;');

	///////////////////////////////////////////////////////////////////////
	$('#json_cmd').keydown(function(e) {
		if (e.keyCode == 13) {					
			var cmd = $("#json_cmd").val();
			$(this).val("");					
					// $("#json_res").text("");					
					
					if (cmd=="clc"){
						console.log('Clear screen');
						$("#json_res").text("");
					}
					else {
						console.log('Sending command: ' + cmd);
						$("#json_res").append("cmd>" + cmd + "\n");
						var psconsole = $('#json_res');
    					psconsole.scrollTop(
        				psconsole[0].scrollHeight - psconsole.height()
    					);
						
						// $.getJSON('/form/', "cmd=" + cmd, function(data) {
						// 	//alert(data);
						// 	$("#json_res").append("res>" + data + "\n");
						// });
					}
		}
	});
	///////////////////////////////////////////////////////////////////////
	$("#console_clear").click(function() {
		console.log('Pressed clear console button');
		$("#json_res").text("");
	});

});