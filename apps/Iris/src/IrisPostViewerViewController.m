// IrisPostViewerViewController.m - Fullscreen media viewer with swipe navigation and actions
#import "IrisPostViewerViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"
#import "IrisCommentsViewController.h"

@interface IrisPostViewerViewController ()

@property (nonatomic, strong) IrisPost *post;
@property (nonatomic, assign) NSInteger currentPostIndex;
@property (nonatomic, strong) UIImageView *imageView;
@property (nonatomic, strong) UIButton *closeButton;
@property (nonatomic, strong) UIView *bottomBar;
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UILabel *userLabel;
@property (nonatomic, strong) UILabel *locationLabel;
@property (nonatomic, strong) UILabel *captionLabel;
@property (nonatomic, strong) UILabel *likesCountLabel;

// Actions
@property (nonatomic, strong) UIButton *likeButton;
@property (nonatomic, strong) UIButton *commentButton;
@property (nonatomic, strong) UIButton *shareButton;
@property (nonatomic, strong) UIButton *bookmarkButton;

@end

@implementation IrisPostViewerViewController

- (instancetype)initWithPost:(IrisPost *)post {
    self = [super init];
    if (self) {
        _post = post;
        _currentPostIndex = [[IrisData sharedData].posts indexOfObject:post];
        if (_currentPostIndex == NSNotFound) _currentPostIndex = 0;
    }
    return self;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor blackColor];
    
    // Main photo centered
    self.imageView = [[UIImageView alloc] initWithFrame:self.view.bounds];
    self.imageView.contentMode = UIViewContentModeScaleAspectFit;
    self.imageView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.imageView.userInteractionEnabled = YES;
    [self.view addSubview:self.imageView];
    
    // Top Close Button
    self.closeButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.closeButton.frame = CGRectMake(16, 44, 40, 40);
    [self.closeButton setImage:[IrisTheme iconNamed:@"close" size:CGSizeMake(24, 24) color:[UIColor whiteColor] filled:NO] forState:UIControlStateNormal];
    [self.closeButton addTarget:self action:@selector(dismissSelf) forControlEvents:UIControlEventTouchUpInside];
    [self.view addSubview:self.closeButton];
    
    // Bottom Overlay Bar (Glass gradient)
    CGFloat barH = 148.0;
    self.bottomBar = [[UIView alloc] initWithFrame:CGRectMake(0, self.view.bounds.size.height - barH, self.view.bounds.size.width, barH)];
    self.bottomBar.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
    self.bottomBar.backgroundColor = [UIColor colorWithWhite:0 alpha:0.75];
    
    // User info
    self.avatarImageView = [[UIImageView alloc] initWithFrame:CGRectMake(16, 12, 34, 34)];
    self.avatarImageView.layer.cornerRadius = 17.0;
    self.avatarImageView.layer.masksToBounds = YES;
    [self.bottomBar addSubview:self.avatarImageView];
    
    self.userLabel = [[UILabel alloc] initWithFrame:CGRectMake(58, 10, self.view.bounds.size.width - 180, 18)];
    self.userLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightBold];
    self.userLabel.textColor = [UIColor whiteColor];
    [self.bottomBar addSubview:self.userLabel];
    
    self.locationLabel = [[UILabel alloc] initWithFrame:CGRectMake(58, 28, self.view.bounds.size.width - 180, 14)];
    self.locationLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightRegular];
    self.locationLabel.textColor = [UIColor colorWithWhite:0.75 alpha:1.0];
    [self.bottomBar addSubview:self.locationLabel];
    
    // Action buttons in bottom bar
    CGFloat actionBtnW = 32.0;
    CGFloat rightX = self.view.bounds.size.width - 14;
    
    self.bookmarkButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.bookmarkButton.frame = CGRectMake(rightX - actionBtnW, 12, actionBtnW, actionBtnW);
    [self.bookmarkButton addTarget:self action:@selector(handleBookmark) forControlEvents:UIControlEventTouchUpInside];
    [self.bottomBar addSubview:self.bookmarkButton];
    rightX -= (actionBtnW + 8);
    
    self.shareButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.shareButton.frame = CGRectMake(rightX - actionBtnW, 12, actionBtnW, actionBtnW);
    [self.shareButton addTarget:self action:@selector(handleShare) forControlEvents:UIControlEventTouchUpInside];
    [self.bottomBar addSubview:self.shareButton];
    rightX -= (actionBtnW + 8);
    
    self.commentButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.commentButton.frame = CGRectMake(rightX - actionBtnW, 12, actionBtnW, actionBtnW);
    [self.commentButton addTarget:self action:@selector(handleComment) forControlEvents:UIControlEventTouchUpInside];
    [self.bottomBar addSubview:self.commentButton];
    rightX -= (actionBtnW + 8);
    
    self.likeButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.likeButton.frame = CGRectMake(rightX - actionBtnW, 12, actionBtnW, actionBtnW);
    [self.likeButton addTarget:self action:@selector(handleLike) forControlEvents:UIControlEventTouchUpInside];
    [self.bottomBar addSubview:self.likeButton];
    
    // Likes count
    self.likesCountLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, 52, self.view.bounds.size.width - 32, 16)];
    self.likesCountLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightSemibold];
    self.likesCountLabel.textColor = [UIColor whiteColor];
    [self.bottomBar addSubview:self.likesCountLabel];
    
    // Caption
    self.captionLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, 72, self.view.bounds.size.width - 32, 38)];
    self.captionLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightRegular];
    self.captionLabel.textColor = [UIColor colorWithWhite:0.92 alpha:1.0];
    self.captionLabel.numberOfLines = 2;
    [self.bottomBar addSubview:self.captionLabel];
    
    [self.view addSubview:self.bottomBar];
    
    // Gestures: swipe down to dismiss, swipe left/right for next/prev post
    UISwipeGestureRecognizer *swipeDown = [[UISwipeGestureRecognizer alloc] initWithTarget:self action:@selector(dismissSelf)];
    swipeDown.direction = UISwipeGestureRecognizerDirectionDown;
    [self.view addGestureRecognizer:swipeDown];
    
    UISwipeGestureRecognizer *swipeLeft = [[UISwipeGestureRecognizer alloc] initWithTarget:self action:@selector(handleSwipeLeft)];
    swipeLeft.direction = UISwipeGestureRecognizerDirectionLeft;
    [self.view addGestureRecognizer:swipeLeft];
    
    UISwipeGestureRecognizer *swipeRight = [[UISwipeGestureRecognizer alloc] initWithTarget:self action:@selector(handleSwipeRight)];
    swipeRight.direction = UISwipeGestureRecognizerDirectionRight;
    [self.view addGestureRecognizer:swipeRight];
    
    [self displayPostAtIndex:self.currentPostIndex];
}

- (void)displayPostAtIndex:(NSInteger)index {
    if (index < 0 || index >= (NSInteger)[IrisData sharedData].posts.count) return;
    self.currentPostIndex = index;
    self.post = [IrisData sharedData].posts[index];
    
    self.userLabel.text = [NSString stringWithFormat:@"@%@", self.post.username];
    self.locationLabel.text = self.post.location;
    self.locationLabel.hidden = (self.post.location.length == 0);
    self.captionLabel.text = self.post.caption;
    
    NSNumberFormatter *fmt = [[NSNumberFormatter alloc] init];
    fmt.numberStyle = NSNumberFormatterDecimalStyle;
    self.likesCountLabel.text = [NSString stringWithFormat:@"%@ likes  •  %ld comments", [fmt stringFromNumber:@(self.post.likes)], (long)self.post.commentsCount];
    
    self.avatarImageView.image = [IrisData imageForKey:self.post.avatar
                                                  size:CGSizeMake(34, 34)
                                                 title:[self.post.username uppercaseString]
                                              subtitle:@""];
    
    self.imageView.image = [IrisData imageForKey:self.post.imageKey
                                            size:self.view.bounds.size
                                           title:self.post.location
                                        subtitle:self.post.username];
    [self updateActionButtonsAnimated:NO];
}

- (void)updateActionButtonsAnimated:(BOOL)animated {
    UIColor *white = [UIColor whiteColor];
    UIColor *likeCol = self.post.isLiked ? [[IrisTheme sharedTheme] errorColor] : white;
    UIColor *bookCol = self.post.isBookmarked ? [[IrisTheme sharedTheme] accentVioletColor] : white;
    
    [self.likeButton setImage:[IrisTheme iconNamed:@"like" size:CGSizeMake(22, 22) color:likeCol filled:self.post.isLiked] forState:UIControlStateNormal];
    [self.commentButton setImage:[IrisTheme iconNamed:@"comment" size:CGSizeMake(22, 22) color:white filled:NO] forState:UIControlStateNormal];
    [self.shareButton setImage:[IrisTheme iconNamed:@"share" size:CGSizeMake(22, 22) color:white filled:NO] forState:UIControlStateNormal];
    [self.bookmarkButton setImage:[IrisTheme iconNamed:@"bookmark" size:CGSizeMake(22, 22) color:bookCol filled:self.post.isBookmarked] forState:UIControlStateNormal];
    
    NSNumberFormatter *fmt = [[NSNumberFormatter alloc] init];
    fmt.numberStyle = NSNumberFormatterDecimalStyle;
    self.likesCountLabel.text = [NSString stringWithFormat:@"%@ likes  •  %ld comments", [fmt stringFromNumber:@(self.post.likes)], (long)self.post.commentsCount];
}

- (void)handleLike {
    [[IrisData sharedData] toggleLikeForPost:self.post];
    [self updateActionButtonsAnimated:YES];
}

- (void)handleBookmark {
    [[IrisData sharedData] toggleBookmarkForPost:self.post];
    [self updateActionButtonsAnimated:NO];
}

- (void)handleComment {
    IrisCommentsViewController *commentsVC = [[IrisCommentsViewController alloc] initWithPost:self.post];
    UINavigationController *nav = [[UINavigationController alloc] initWithRootViewController:commentsVC];
    [self presentViewController:nav animated:YES completion:nil];
}

- (void)handleShare {
    UIAlertController *sheet = [UIAlertController alertControllerWithTitle:[NSString stringWithFormat:@"Share @%@'s Post", self.post.username]
                                                                   message:nil
                                                            preferredStyle:UIAlertControllerStyleActionSheet];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Copy Link" style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
        UIPasteboard.generalPasteboard.string = [NSString stringWithFormat:@"https://iris.social/p/%@", self.post.postId];
    }]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Send via Iris Direct" style:UIAlertActionStyleDefault handler:nil]];
    [sheet addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [self presentViewController:sheet animated:YES completion:nil];
}

- (void)handleSwipeLeft {
    if (self.currentPostIndex < (NSInteger)[IrisData sharedData].posts.count - 1) {
        [self displayPostAtIndex:self.currentPostIndex + 1];
    }
}

- (void)handleSwipeRight {
    if (self.currentPostIndex > 0) {
        [self displayPostAtIndex:self.currentPostIndex - 1];
    }
}

- (void)dismissSelf {
    [self dismissViewControllerAnimated:YES completion:nil];
}

@end
