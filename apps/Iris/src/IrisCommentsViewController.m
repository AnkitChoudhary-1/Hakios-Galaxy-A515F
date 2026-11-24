// IrisCommentsViewController.m
#import "IrisCommentsViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"

@interface IrisCommentCell : UITableViewCell
@property (nonatomic, strong) UIImageView *avatarImageView;
@property (nonatomic, strong) UILabel *usernameLabel;
@property (nonatomic, strong) UILabel *commentLabel;
@property (nonatomic, strong) UILabel *timeLabel;
@property (nonatomic, strong) UIButton *likeButton;
@property (nonatomic, strong) IrisComment *comment;
@property (nonatomic, copy) void (^likeToggleHandler)(void);
- (void)configureWithComment:(IrisComment *)comment;
@end

@implementation IrisCommentCell

- (instancetype)initWithStyle:(UITableViewCellStyle)style reuseIdentifier:(NSString *)reuseIdentifier {
    self = [super initWithStyle:style reuseIdentifier:reuseIdentifier];
    if (self) {
        self.selectionStyle = UITableViewCellSelectionStyleNone;
        self.backgroundColor = [UIColor clearColor];
        self.contentView.backgroundColor = [UIColor clearColor];
        
        self.avatarImageView = [[UIImageView alloc] initWithFrame:CGRectMake(14, 10, 34, 34)];
        self.avatarImageView.layer.cornerRadius = 17.0;
        self.avatarImageView.layer.masksToBounds = YES;
        [self.contentView addSubview:self.avatarImageView];
        
        self.usernameLabel = [[UILabel alloc] init];
        self.usernameLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightSemibold];
        self.usernameLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
        [self.contentView addSubview:self.usernameLabel];
        
        self.commentLabel = [[UILabel alloc] init];
        self.commentLabel.font = [UIFont systemFontOfSize:13 weight:UIFontWeightRegular];
        self.commentLabel.numberOfLines = 0;
        self.commentLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
        [self.contentView addSubview:self.commentLabel];
        
        self.timeLabel = [[UILabel alloc] init];
        self.timeLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightRegular];
        self.timeLabel.textColor = [[IrisTheme sharedTheme] mutedTextColor];
        [self.contentView addSubview:self.timeLabel];
        
        self.likeButton = [UIButton buttonWithType:UIButtonTypeCustom];
        [self.likeButton addTarget:self action:@selector(handleLikeTapped) forControlEvents:UIControlEventTouchUpInside];
        [self.contentView addSubview:self.likeButton];
    }
    return self;
}

- (void)configureWithComment:(IrisComment *)comment {
    _comment = comment;
    self.usernameLabel.text = comment.username;
    self.commentLabel.text = comment.text;
    self.timeLabel.text = comment.timestamp;
    
    self.avatarImageView.image = [IrisData imageForKey:comment.avatar
                                                  size:CGSizeMake(34, 34)
                                                 title:[comment.username uppercaseString]
                                              subtitle:@""];
    
    UIColor *heartColor = comment.isLiked ? [[IrisTheme sharedTheme] errorColor] : [[IrisTheme sharedTheme] mutedTextColor];
    UIImage *img = [IrisTheme iconNamed:@"like" size:CGSizeMake(14, 14) color:heartColor filled:comment.isLiked];
    [self.likeButton setImage:img forState:UIControlStateNormal];
    [self setNeedsLayout];
}

- (void)layoutSubviews {
    [super layoutSubviews];
    CGFloat w = self.contentView.bounds.size.width;
    CGFloat rightPad = 48.0;
    
    self.avatarImageView.frame = CGRectMake(14, 10, 34, 34);
    
    self.usernameLabel.frame = CGRectMake(58, 10, w - 58 - rightPad, 18);
    
    CGSize txtSize = [self.commentLabel sizeThatFits:CGSizeMake(w - 58 - rightPad, CGFLOAT_MAX)];
    self.commentLabel.frame = CGRectMake(58, 30, w - 58 - rightPad, txtSize.height);
    
    self.timeLabel.frame = CGRectMake(58, CGRectGetMaxY(self.commentLabel.frame) + 4, 120, 14);
    
    self.likeButton.frame = CGRectMake(w - 40, 14, 28, 28);
}

- (void)handleLikeTapped {
    self.comment.isLiked = !self.comment.isLiked;
    self.comment.likes += self.comment.isLiked ? 1 : -1;
    UIColor *heartColor = self.comment.isLiked ? [[IrisTheme sharedTheme] errorColor] : [[IrisTheme sharedTheme] mutedTextColor];
    UIImage *img = [IrisTheme iconNamed:@"like" size:CGSizeMake(14, 14) color:heartColor filled:self.comment.isLiked];
    [self.likeButton setImage:img forState:UIControlStateNormal];
}

@end

@interface IrisCommentsViewController () <UITableViewDataSource, UITableViewDelegate, UITextFieldDelegate>

@property (nonatomic, strong) IrisPost *post;
@property (nonatomic, strong) UITableView *tableView;
@property (nonatomic, strong) UIView *inputContainer;
@property (nonatomic, strong) UITextField *textField;
@property (nonatomic, strong) UIButton *sendButton;

@end

@implementation IrisCommentsViewController

- (instancetype)initWithPost:(IrisPost *)post {
    self = [super init];
    if (self) {
        _post = post;
    }
    return self;
}

- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Comments";
    self.view.backgroundColor = [[IrisTheme sharedTheme] secondaryBackgroundColor];
    
    UIBarButtonItem *closeItem = [[UIBarButtonItem alloc] initWithTitle:@"Done"
                                                                  style:UIBarButtonItemStyleDone
                                                                 target:self
                                                                 action:@selector(dismissSelf)];
    self.navigationItem.rightBarButtonItem = closeItem;
    
    CGFloat inputH = 56.0;
    CGFloat bottomPad = 20.0;
    
    self.tableView = [[UITableView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, self.view.bounds.size.height - inputH - bottomPad) style:UITableViewStylePlain];
    self.tableView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.tableView.backgroundColor = [UIColor clearColor];
    self.tableView.separatorStyle = UITableViewCellSeparatorStyleNone;
    self.tableView.dataSource = self;
    self.tableView.delegate = self;
    [self.tableView registerClass:[IrisCommentCell class] forCellReuseIdentifier:@"IrisCommentCell"];
    [self.view addSubview:self.tableView];
    
    // Bottom input bar
    self.inputContainer = [[UIView alloc] initWithFrame:CGRectMake(0, self.view.bounds.size.height - inputH - bottomPad, self.view.bounds.size.width, inputH + bottomPad)];
    self.inputContainer.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleTopMargin;
    self.inputContainer.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    
    UIView *topLine = [[UIView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, 0.5)];
    topLine.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    topLine.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [self.inputContainer addSubview:topLine];
    
    self.textField = [[UITextField alloc] initWithFrame:CGRectMake(16, 8, self.view.bounds.size.width - 80, 40)];
    self.textField.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.textField.placeholder = @"Add a comment...";
    self.textField.font = [UIFont systemFontOfSize:14];
    self.textField.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.textField.delegate = self;
    [self.inputContainer addSubview:self.textField];
    
    self.sendButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.sendButton.frame = CGRectMake(self.view.bounds.size.width - 64, 8, 52, 40);
    self.sendButton.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin;
    [self.sendButton setTitle:@"Post" forState:UIControlStateNormal];
    [self.sendButton setTitleColor:[[IrisTheme sharedTheme] accentVioletColor] forState:UIControlStateNormal];
    self.sendButton.titleLabel.font = [UIFont systemFontOfSize:14 weight:UIFontWeightSemibold];
    [self.sendButton addTarget:self action:@selector(sendComment) forControlEvents:UIControlEventTouchUpInside];
    [self.inputContainer addSubview:self.sendButton];
    
    [self.view addSubview:self.inputContainer];
}

- (void)dismissSelf {
    [self dismissViewControllerAnimated:YES completion:nil];
}

- (void)sendComment {
    NSString *text = [self.textField.text stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if (text.length == 0) return;
    
    [[IrisData sharedData] addComment:text toPost:self.post];
    self.textField.text = @"";
    [self.textField resignFirstResponder];
    [self.tableView reloadData];
    
    if (self.post.comments.count > 0) {
        NSIndexPath *lastPath = [NSIndexPath indexPathForRow:self.post.comments.count - 1 inSection:0];
        [self.tableView scrollToRowAtIndexPath:lastPath atScrollPosition:UITableViewScrollPositionBottom animated:YES];
    }
}

- (BOOL)textFieldShouldReturn:(UITextField *)textField {
    [self sendComment];
    return YES;
}

#pragma mark - Table View

- (NSInteger)tableView:(UITableView *)tableView numberOfRowsInSection:(NSInteger)section {
    return self.post.comments.count;
}

- (CGFloat)tableView:(UITableView *)tableView heightForRowAtIndexPath:(NSIndexPath *)indexPath {
    IrisComment *c = self.post.comments[indexPath.row];
    CGFloat w = tableView.bounds.size.width - 58 - 48;
    CGRect r = [c.text boundingRectWithSize:CGSizeMake(w, CGFLOAT_MAX)
                                    options:NSStringDrawingUsesLineFragmentOrigin
                                 attributes:@{NSFontAttributeName: [UIFont systemFontOfSize:13]}
                                    context:nil];
    return ceil(30 + r.size.height + 26);
}

- (UITableViewCell *)tableView:(UITableView *)tableView cellForRowAtIndexPath:(NSIndexPath *)indexPath {
    IrisCommentCell *cell = [tableView dequeueReusableCellWithIdentifier:@"IrisCommentCell" forIndexPath:indexPath];
    IrisComment *c = self.post.comments[indexPath.row];
    [cell configureWithComment:c];
    return cell;
}

@end
