$(function(){
    $('#letsCook').click(function(){
        
        $.ajax({
            url: '/recipe-list',
            data: $('form').serialize(),
            type: 'POST',
            success: function(response){
                console.log(response);
            },
            error: function(error){
                console.log(error);
            }
        });
    });
});