<?php
    if(substr_count($_SERVER['HTTP_USER_AGENT'], 'Firefox')===0){
        header('Location: notfx.htm');
    }else{
        header('Location: fx.htm');
    }
?>